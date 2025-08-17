"""
Python tools module.
This module provides tools for managing Unreal Python API interactions.
"""

import logging
from typing import Dict, Any
import os

from mcp.server.fastmcp import FastMCP, Context

# Get logger
logger = logging.getLogger("UnrealMCP")

def register_python_tools(mcp: FastMCP):
    """Register Python tools with the MCP server."""

    @mcp.tool()
    def execute_python_script(ctx: Context, script: str | None, path: str | None) -> Dict[str, Any]:
        """
        Execute a Python script in the Unreal Engine context.

        Args:
            script: The Python script to execute, would be executed if provided
            path: The optional path to the Python script file, only be executed if script is None

        Returns:
            Response indicating success or failure
        """
        from unreal_mcp_server import get_unreal_connection

        try:
            unreal = get_unreal_connection()
            if not unreal:
                logger.error("Failed to connect to Unreal Engine")
                return {"success": False, "message": "Failed to connect to Unreal Engine"}

            params = {"script": script, "path": path}

            # Check valid parameters
            if not script and not path:
                error_msg = "Either script or path must be provided"
                logger.error(error_msg)
                return {"success": False, "message": error_msg}
            if os.path.isfile(path) is False and path is not None:
                error_msg = f"Script file does not exist: {path}"
                logger.error(error_msg)
                return {"success": False, "message": error_msg}

            # if path is relative, convert to absolute path
            if path and not os.path.isabs(path):
                path = os.path.abspath(path)

            params = {"script": script, "path": path}
            response = unreal.send_command("execute_python_script", params)

            if not response:
                logger.error("No response from Unreal Engine")
                return {"success": False, "message": "No response from Unreal Engine"}

            logger.info(f"Python script execution response: {response}")
            return response

        except Exception as e:
            error_msg = f"Error executing Python script: {e}"
            logger.error(error_msg)
            return {"success": False, "message": error_msg}

    @mcp.tool()
    def save_python_script(ctx: Context, script: str, path: str) -> Dict[str, Any]:
        """
        Save a Python script to a specified path in the Unreal Engine context. No need to connect to Unreal.

        Args:
            script: The Python script content
        """
        try:
            with open(path, 'w') as file:
                file.write(script)
            return {"success": True, "message": "Script saved successfully"}
        except Exception as e:
            error_msg = f"Error saving Python script: {e}"
            logger.error(error_msg)
            return {"success": False, "message": error_msg}

    logger.info("Python tools registered successfully")

    @mcp.tool()
    def list_python_scripts(ctx: Context, directory: str) -> Dict[str, Any]:
        """
        List all Python scripts in a specified directory.

        Args:
            directory: The directory to list scripts from

        Returns:
            List of Python script filenames
        """
        import os

        try:
            if not os.path.isdir(directory):
                error_msg = f"Directory does not exist: {directory}"
                logger.error(error_msg)
                return {"success": False, "message": error_msg}

            scripts = [f for f in os.listdir(directory) if f.endswith('.py')]
            return {"success": True, "scripts": scripts}
        except Exception as e:
            error_msg = f"Error listing Python scripts: {e}"
            logger.error(error_msg)
            return {"success": False, "message": error_msg}
    logger.info("Python tools registered successfully")

if __name__ == "__main__":
    import asyncio
    from fastmcp import Client, FastMCP

    # Configure logging for testing
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    async def test_list_python_scripts():
        """Test the list_python_scripts functionality"""
        # 创建 MCP 服务器
        mcp = FastMCP()
        register_python_tools(mcp)  # 注册工具

        # 使用 Client 连接到 MCP 服务器
        async with Client(mcp) as client:
            print("=== Testing list_python_scripts functionality ===\n")

            # Test 1: Valid directory
            test_dir = "D:\\Playground\\unreal_mcp\\test_scripts"
            print(f"Test 1: Listing Python scripts in valid directory: {test_dir}")
            try:
                response = await client.call_tool("list_python_scripts", {
                    "ctx": {},
                    "directory": test_dir
                })
                print(f"Response type: {type(response)}")
                print(f"Response: {response}")

                # Access the content from CallToolResult
                result = response.content[0].text if response.content else "{}"
                import json
                result_dict = json.loads(result)

                if result_dict.get("success"):
                    scripts = result_dict.get("scripts", [])
                    print(f"Found {len(scripts)} Python scripts:")
                    for script in scripts:
                        print(f"  - {script}")
                else:
                    print(f"Error: {result_dict.get('message')}")
            except Exception as e:
                print(f"Exception occurred: {e}")

            print("\n" + "="*50 + "\n")

            # Test 2: Invalid directory
            invalid_dir = "D:\\NonExistent\\Directory"
            print(f"Test 2: Listing Python scripts in invalid directory: {invalid_dir}")
            try:
                response = await client.call_tool("list_python_scripts", {
                    "ctx": {},
                    "directory": invalid_dir
                })
                print(f"Response: {response}")

                # Access the content from CallToolResult
                result = response.content[0].text if response.content else "{}"
                import json
                result_dict = json.loads(result)

                if not result_dict.get("success"):
                    print(f"Expected error message: {result_dict.get('message')}")
            except Exception as e:
                print(f"Exception occurred: {e}")

            print("\n" + "="*50 + "\n")

            # Test 3: scripts directory
            scripts_dir = "D:\\Playground\\unreal_mcp\\Python\\scripts"
            print(f"Test 3: Listing Python scripts in scripts directory: {scripts_dir}")
            try:
                response = await client.call_tool("list_python_scripts", {
                    "ctx": {},
                    "directory": scripts_dir
                })
                print(f"Response: {response}")

                # Access the content from CallToolResult
                result = response.content[0].text if response.content else "{}"
                import json
                result_dict = json.loads(result)

                if result_dict.get("success"):
                    scripts = result_dict.get("scripts", [])
                    print(f"Found {len(scripts)} Python scripts:")
                    for script in scripts:
                        print(f"  - {script}")
            except Exception as e:
                print(f"Exception occurred: {e}")

    asyncio.run(test_list_python_scripts())