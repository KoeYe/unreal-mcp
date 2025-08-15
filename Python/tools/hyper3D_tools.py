"""
Hyper3D tools module.
This module provides tools for managing Hyper3D API interactions.
"""

import logging
from typing import Dict, Any
import requests
import time
from typing import List
import os

from mcp.server.fastmcp import FastMCP, Context

# Get logger
logger = logging.getLogger("Hyper3DMCP")

# Constants
ENDPOINT = "https://api.hyper3d.com/api/v2"
API_KEY = "X5Soz6ehrrMu4nZ73Nr1jFkLNkc98lOE1LcD2IEA11Ba1Xr6JXFrBEfEPQxwR07S"  # Replace with your actual API key
RESULT_PATH = "D:\\Playground\\unreal_mcp\\test_assets"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Function to submit a task to the rodin endpoint
def submit_task(prompt: str):
    url = f"{ENDPOINT}/rodin"

    # Set the tier to Rodin Regular
    data = {
        "prompt": prompt,
        "tier": "Regular"  # Add tier specification
    }

    # Prepare the headers.
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    logger.info(f"Submitting task to {url} with data: {data}")
    response = requests.post(url, json=data, headers=headers)

    # Accept both 200 (OK) and 201 (Created) as successful responses
    if response.status_code not in [200, 201]:
        logger.error(f"HTTP error {response.status_code}: {response.text}")
        return {"error": f"HTTP {response.status_code}: {response.text}"}

    return response.json()
 
def check_status(subscription_key):
    url = f"{ENDPOINT}/status"
    data = {
        "subscription_key": subscription_key
    }
    response = requests.post(url, headers=headers, json=data)

    return response.json()

# Function to download the results of a task
def download_results(task_uuid):
    url = f"{ENDPOINT}/download"
    data = {
        "task_uuid": task_uuid
    }
    response = requests.post(url, headers=headers, json=data)
    return response.json()

def register_hyper3d_tools(mcp: FastMCP):
    @mcp.tool()
    def hyper3d_tool(ctx: Context, prompt: str, path: str = RESULT_PATH) -> Dict[str, Any]:
        """
        Submit a job to Hyper3D and then download to the given path.

        Args:
            ctx: The MCP context
            prompt: The text prompt for generating 3D model (e.g., "Generate a simple cube", "Create a car model")
            path: The local path to save downloaded files (default: uses RESULT_PATH)

        Returns:
            Response indicating success or failure with downloaded file paths

        Examples:
            hyper3d_tool(ctx, "Generate a red sports car", "C:/models/")
            hyper3d_tool(ctx, "Create a medieval castle")
        """
        # Handle default path
        if path is None:
            path = RESULT_PATH

        logger.info(f"Starting Hyper3D generation with prompt: '{prompt}'")

        # Submit the task and get the task UUID
        task_response = submit_task(prompt)
        if 'error' in task_response and task_response['error'] is not None:
            error_msg = f"Error submitting task: {task_response['error']}"
            logger.error(error_msg)
            return {"success": False, "message": error_msg}

        if 'uuid' not in task_response:
            error_msg = f"Invalid response format: {task_response}"
            logger.error(error_msg)
            return {"success": False, "message": error_msg}

        task_uuid = task_response['uuid']
        subscription_key = task_response['jobs']['subscription_key']
        logger.info(f"Task submitted successfully. UUID: {task_uuid}")

        # Poll the status endpoint every 5 seconds until the task is done
        status = []
        while len(status) == 0 or not all(s['status'] in ['Done', 'Failed'] for s in status):
            time.sleep(5)
            status_response = check_status(subscription_key)
            status = status_response['jobs']
            for s in status:
                logger.info(f"Job {s['uuid']}: {s['status']}")
                print(f"job {s['uuid']}: {s['status']}")

        # Download the results once the task is done
        download_response = download_results(task_uuid)
        download_items = download_response['list']

        downloaded_files = []
        # Print the download URLs and download them locally.
        for item in download_items:
            print(f"File Name: {item['name']}, URL: {item['url']}")
            dest_fname = os.path.join(path, item['name'])
            os.makedirs(os.path.dirname(dest_fname), exist_ok=True)
            with open(dest_fname, 'wb') as f:
                response = requests.get(item['url'])
                f.write(response.content)
                print(f"Downloaded {dest_fname}")
                downloaded_files.append(dest_fname)

        return {
            "success": True,
            "message": f"Successfully generated and downloaded {len(downloaded_files)} files",
            "files": downloaded_files
        }

if __name__ == "__main__":
    import asyncio
    from fastmcp import Client, FastMCP

    # Configure logging for testing
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    async def test_mcp_functionality():
        # 创建 MCP 服务器
        mcp = FastMCP()
        register_hyper3d_tools(mcp)  # 注册工具

        # 使用 Client 连接到 MCP 服务器
        async with Client(mcp) as client:
            # 调用名为 'hyper3d_tool' 的工具
            response = await client.call_tool("hyper3d_tool", {
                "ctx": {},
                "prompt": "Generate a simple 3D cube",
                "path": "D:\\Playground\\unreal_mcp\\test_assets"
            })
            # 打印响应结果
            print("Response:", response)
            # 检查返回结果
            if hasattr(response, 'data') and response.data.get("success"):
                print("3D model generated successfully!")
                print(f"Downloaded files: {response.data.get('files', [])}")
            else:
                print("Failed to generate 3D model.")
                if hasattr(response, 'data'):
                    print(f"Error: {response.data.get('message', 'Unknown error')}")

    asyncio.run(test_mcp_functionality())