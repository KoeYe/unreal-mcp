"""
Python tools module.
This module provides tools for managing Unreal Python API interactions.
"""

import logging
from typing import Dict, Any, Optional
import os

from mcp.server.fastmcp import FastMCP, Context

# Get logger
logger = logging.getLogger("UnrealMCP")

def register_python_tools(mcp: FastMCP):
    """Register Python tools with the MCP server."""

    @mcp.tool()
    def execute_python_script(ctx: Context, script: Optional[str] = None, path: Optional[str] = None) -> Dict[str, Any]:
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

            # Ensure at least one parameter is provided
            if not script and not path:
                error_msg = "Either script or path must be provided"
                logger.error(error_msg)
                return {"success": False, "message": error_msg}

            # If path is provided, validate it
            if path and not os.path.isfile(path):
                error_msg = f"Script file does not exist: {path}"
                logger.error(error_msg)
                return {"success": False, "message": error_msg}

            # if path is relative, convert to absolute path
            if path and not os.path.isabs(path):
                path = os.path.abspath(path)

            # if only path is offered, read and convert to script
            if script is None and path:
                with open(path, 'r') as file:
                    script = file.read()

            # Only send script content to Unreal
            response = unreal.send_command("execute_python_script", {"script": script})

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
    def list_python_scripts(ctx: Context, path: str) -> Dict[str, Any]:
        """
        List all Python scripts in a specified path.

        Args:
            path: The directory to list scripts from

        Returns:
            List of Python script filenames
        """
        import os

        try:
            if not os.path.isdir(path):
                error_msg = f"Path does not exist: {path}"
                logger.error(error_msg)
                return {"success": False, "message": error_msg}

            scripts = [f for f in os.listdir(path) if f.endswith('.py')]
            return {"success": True, "scripts": scripts}
        except Exception as e:
            error_msg = f"Error listing Python scripts: {e}"
            logger.error(error_msg)
            return {"success": False, "message": error_msg}
    logger.info("Python tools registered successfully")

    @mcp.tool()
    def read_python_file(ctx: Context, path: str) -> Dict[str, Any]:
        """
        Read a Python script from a specified path in the Unreal Engine context. No need to connect to Unreal.

        Args:
            path: The path to the Python script file

        Returns:
            The content of the Python script or an error message
        """
        try:
            with open(path, 'r') as file:
                script = file.read()
            return {"success": True, "script": script}
        except Exception as e:
            error_msg = f"Error reading Python script: {e}"
            logger.error(error_msg)
            return {"success": False, "message": error_msg}
        
    @mcp.tool()
    def read_saved_images(ctx: Context) -> Dict[str, Any]:
        """
        Read saved images from the Unreal Engine context. No need to connect to Unreal. Defaultly read all images under /workspace/images.

        Returns:
            List of saved image filenames and paths
        """
        try:
            # 默认图片目录
            ws = os.environ.get("WORK_SPACE")
            if not ws or not ws.strip():
                ws = "/data/koe/coding-agent-ue/Saved"
            default_image_dir = os.path.join(ws, "images")
            if not default_image_dir or not default_image_dir.strip():
                return {"success": False, "message": "Image directory is not set in WORK_SPACE environment variable."}

            # 支持的图片格式
            image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif', '.svg'}
            
            # 检查目录是否存在
            if not os.path.exists(default_image_dir):
                logger.warning(f"Image directory does not exist: {default_image_dir}")
                return {
                    "success": True, 
                    "message": f"Image directory does not exist: {default_image_dir}",
                    "images": [],
                    "image_paths": []
                }
            
            if not os.path.isdir(default_image_dir):
                error_msg = f"Path is not a directory: {default_image_dir}"
                logger.error(error_msg)
                return {"success": False, "message": error_msg}
            
            # 获取所有图片文件
            image_files = []
            image_paths = []
            
            for filename in os.listdir(default_image_dir):
                file_path = os.path.join(default_image_dir, filename)
                
                # 检查是否为文件且有图片扩展名
                if (os.path.isfile(file_path) and 
                    any(filename.lower().endswith(ext) for ext in image_extensions)):
                    image_files.append(filename)
                    image_paths.append(file_path)
            
            # 按文件名排序
            sorted_pairs = sorted(zip(image_files, image_paths))
            image_files = [pair[0] for pair in sorted_pairs]
            image_paths = [pair[1] for pair in sorted_pairs]
            
            logger.info(f"Found {len(image_files)} image files in {default_image_dir}")
            
            # 返回符合 OpenHands 格式的响应
            return {
                "success": True,
                "message": f"Found {len(image_files)} image files in {default_image_dir}",
                "images": image_files,
                "image_paths": image_paths,  # 关键：OpenHands 会识别这个字段
                "directory": default_image_dir,
                "count": len(image_files)
            }
            
        except Exception as e:
            error_msg = f"Error reading saved images: {e}"
            logger.error(error_msg)
            return {"success": False, "message": error_msg}

    @mcp.tool()
    def get_camera_0_view(ctx: Context) -> Dict[str, Any]:
        """
        Get the current view from camera 0 in the Unreal Engine context.

        Returns:
            The image data from camera 0 or an error message
        """
        from unreal_mcp_server import get_unreal_connection
        import re

        try:
            unreal = get_unreal_connection()
            if not unreal:
                logger.error("Failed to connect to Unreal Engine")
                return {"success": False, "message": "Failed to connect to Unreal Engine"}

            with open('/home/koe/unreal-mcp/Python/utils/get_camera_0_view_script.py') as f: # TODO: remove this hardcode!!
                script = f.read()
            response = unreal.send_command("execute_python_script",  {"script": script})

            if not response:
                logger.error("No response from Unreal Engine")
                return {"success": False, "message": "No response from Unreal Engine"}

            logger.info(f"Camera 0 view response: {response}")
            
            # Extract image path from python_logs
            image_paths = []
            if response.get('status') == 'success':
                image_paths = ['/data/koe/coding-agent-ue/Saved/images/currentimage.png'] # TODO: remove this hardcode!!
            
            # Return in format compatible with OpenHands MCPObservation
            if image_paths:
                return {
                    "success": True,
                    "message": "Camera view captured successfully",
                    "image_paths": image_paths,  # This is the key field OpenHands looks for
                    "original_response": response
                }
            else:
                return {
                    "success": True,
                    "message": "Camera view executed but no image path found",
                    "image_paths": [],
                    "original_response": response
                }

        except Exception as e:
            error_msg = f"Error getting camera 0 view: {e}"
            logger.error(error_msg)
            return {"success": False, "message": error_msg}
            

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
