"""
Python tools module for Unreal MCP.
Provides read-only Python tool execution and image capture with base64 output.
"""

import logging
from typing import Dict, Any, Optional
import os
import io
import base64
from PIL import Image

from mcp.server.fastmcp import FastMCP, Context

logger = logging.getLogger("UnrealMCP")

DEFAULT_PYTHON_DIR = os.getenv("PROJ_DIR", "/opt/coding-agent-ue") + "/Content/Python"
DEFAULT_IMAGE_DIR = os.getenv("PROJ_DIR", "/opt/coding-agent-ue") + "/Saved/images"

def compress_image_to_base64(image_path: str, quality: int = 70) -> str:
    """Compress an image to JPEG and return as base64 string."""
    with Image.open(image_path) as img:
        buffer = io.BytesIO()
        img.convert("RGB").save(buffer, format="JPEG", quality=quality)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

def register_python_tools(mcp: FastMCP):
    """Register Python-related tools with the MCP server."""

    @mcp.tool()
    def execute_python_script(ctx: Context, script: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute a Python script string in Unreal Engine context.
        Agent submits script directly; no path needed.
        """
        from unreal_mcp_server import get_unreal_connection
        try:
            unreal = get_unreal_connection()
            if not unreal:
                return {"success": False, "message": "Failed to connect to Unreal Engine"}

            if not script:
                return {"success": False, "message": "Script must be provided"}

            response = unreal.send_command("execute_python_script", {"script": script})
            if not response:
                return {"success": False, "message": "No response from Unreal Engine"}

            return {"success": True, "message": "Script executed", "response": response}

        except Exception as e:
            logger.error(f"Error executing Python script: {e}")
            return {"success": False, "message": str(e)}

    @mcp.tool()
    def list_python_scripts(ctx: Context) -> Dict[str, Any]:
        """List all read-only Python scripts in DEFAULT_PYTHON_DIR."""
        try:
            if not os.path.isdir(DEFAULT_PYTHON_DIR):
                return {"success": False, "message": f"Python directory does not exist: {DEFAULT_PYTHON_DIR}", "scripts": []}
            scripts = sorted(f for f in os.listdir(DEFAULT_PYTHON_DIR) if f.endswith('.py'))
            return {"success": True, "message": f"Found {len(scripts)} scripts", "scripts": scripts}
        except Exception as e:
            logger.error(f"Error listing Python scripts: {e}")
            return {"success": False, "message": str(e), "scripts": []}

    @mcp.tool()
    def read_python_file(ctx: Context, filename: str) -> Dict[str, Any]:
        """Read a Python script from DEFAULT_PYTHON_DIR (read-only)."""
        try:
            file_path = os.path.join(DEFAULT_PYTHON_DIR, filename)
            if not os.path.isfile(file_path):
                return {"success": False, "message": f"File not found: {filename}", "script": ""}
            with open(file_path, 'r') as f:
                script = f.read()
            return {"success": True, "message": "Script read successfully", "script": script}
        except Exception as e:
            logger.error(f"Error reading Python script: {e}")
            return {"success": False, "message": str(e), "script": ""}

    @mcp.tool()
    def read_saved_images(ctx: Context) -> Dict[str, Any]:
        """Return all images in DEFAULT_IMAGE_DIR as compressed base64."""
        try:
            if not os.path.isdir(DEFAULT_IMAGE_DIR):
                return {"success": False, "message": f"Image directory does not exist: {DEFAULT_IMAGE_DIR}", "images": []}

            image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif', '.svg'}
            images_b64 = []

            for filename in sorted(os.listdir(DEFAULT_IMAGE_DIR)):
                file_path = os.path.join(DEFAULT_IMAGE_DIR, filename)
                if os.path.isfile(file_path) and any(filename.lower().endswith(ext) for ext in image_extensions):
                    try:
                        b64 = compress_image_to_base64(file_path, quality=70)
                        images_b64.append({"name": filename, "base64": b64})
                    except Exception as e:
                        logger.warning(f"Failed to compress image {filename}: {e}")

            return {"success": True, "message": f"Found {len(images_b64)} images", "images": images_b64}
        except Exception as e:
            logger.error(f"Error reading images: {e}")
            return {"success": False, "message": str(e), "images": []}

    @mcp.tool()
    def get_camera_0_view(ctx: Context) -> Dict[str, Any]:
        """
        Capture camera 0 view, save to DEFAULT_IMAGE_DIR/currentimage.png,
        compress and return base64.
        """
        from unreal_mcp_server import get_unreal_connection
        try:
            unreal = get_unreal_connection()
            if not unreal:
                return {"success": False, "message": "Failed to connect to Unreal Engine", "base64": ""}

            script_path = os.path.join(DEFAULT_PYTHON_DIR, "get_camera_0_view_script.py")
            if not os.path.isfile(script_path):
                return {"success": False, "message": f"Camera script not found: {script_path}", "base64": ""}

            with open(script_path, 'r') as f:
                script = f.read()

            response = unreal.send_command("execute_python_script", {"script": script})
            if not response or response.get("status") != "success":
                return {"success": False, "message": "Failed to execute camera script", "base64": ""}

            image_file = os.path.join(DEFAULT_IMAGE_DIR, "currentimage.png")
            if not os.path.isfile(image_file):
                return {"success": False, "message": f"Camera image not found", "base64": ""}

            img_b64 = compress_image_to_base64(image_file, quality=70)
            return {"success": True, "message": "Camera view captured", "base64": img_b64}

        except Exception as e:
            logger.error(f"Error getting camera 0 view: {e}")
            return {"success": False, "message": str(e), "base64": ""}
