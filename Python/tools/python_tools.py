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

import mcp
from mcp.server.fastmcp import FastMCP, Context

logger = logging.getLogger("UnrealMCP")

DEFAULT_UE_PROJ_ROOT = os.getenv("UE_PROJ_DIR", "/opt/coding-agent-ue")
DEFAULT_PYTHON_DIR = os.getenv("PROJ_DIR", "/opt/coding-agent-ue") + "/Content/Python"
DEFAULT_IMAGE_DIR = os.getenv("PROJ_DIR", "/opt/coding-agent-ue") + "/Saved/images"

def compress_image_to_base64(image_path: str, quality: int = 70) -> str:
    """Compress an image to JPEG and return as base64 string."""
    with Image.open(image_path) as img:
        buffer = io.BytesIO()
        img.convert("RGB").save(buffer, format="JPEG", quality=quality)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    @mcp.tool()
    def execute_python_script(ctx: Context, script: Optional[str] = None, path: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a Python script in Unreal Engine context.
        Either `script` or `path` must be provided.
        If `script` is provided, it is executed directly.
        If `path` is provided, the file content is read and executed.
        The `path` is relative to the Unreal Engine project root.
        The `params` dictionary is used to replace ${variable} placeholders in the script.
        """
        from unreal_mcp_server import get_unreal_connection
        import os
        import re
        import json

        try:
            unreal = get_unreal_connection()
            if not unreal:
                return {"success": False, "message": "Failed to connect to Unreal Engine"}

            # Prepare script
            if script:
                final_script = script
            elif path:
                if not DEFAULT_UE_PROJ_ROOT:
                    return {"success": False, "message": "Environment variable 'UE_PROJ_DIR' is not set"}

                full_path = os.path.join(DEFAULT_UE_PROJ_ROOT, path)
                if not os.path.isfile(full_path):
                    return {"success": False, "message": f"File not found: {full_path}"}

                with open(full_path, "r", encoding="utf-8") as f:
                    final_script = f.read()
            else:
                return {"success": False, "message": "Either 'script' or 'path' must be provided"}

            # Process parameters if provided
            if params:
                # Find all ${variable} patterns in the script
                template_vars = re.findall(r'\$\{(\w+)\}', final_script)
                
                if template_vars:
                    # Check if all required parameters are provided
                    missing_params = [var for var in template_vars if var not in params]
                    if missing_params:
                        return {
                            "success": False, 
                            "message": f"Missing required parameters: {', '.join(missing_params)}",
                            "required_params": template_vars,
                            "provided_params": list(params.keys()),
                            "missing_params": missing_params
                        }
                    
                    # Replace all ${variable} with actual values
                    for var_name in template_vars:
                        var_value = params[var_name]
                        # Convert value to appropriate string representation
                        if isinstance(var_value, (dict, list)):
                            var_str = json.dumps(var_value)
                        elif isinstance(var_value, str):
                            var_str = var_value
                        else:
                            var_str = str(var_value)
                        
                        final_script = final_script.replace(f"${{{var_name}}}", var_str)

            # Check if there are still unresolved template variables
            remaining_vars = re.findall(r'\$\{(\w+)\}', final_script)
            if remaining_vars:
                return {
                    "success": False,
                    "message": f"Unresolved template variables: {', '.join(remaining_vars)}",
                    "unresolved_vars": remaining_vars
                }

            # submit
            response = unreal.send_command("execute_python_script", {"script": final_script})
            if not response:
                return {"success": False, "message": "No response from Unreal Engine"}

            return {"success": True, "message": "Script executed", "response": response}

        except Exception as e:
            logger.error(f"Error executing Python script: {e}")
            return {"success": False, "message": str(e)}


    @mcp.tool()
    def list_python_scripts(ctx: Context) -> Dict[str, Any]:
        """List all UE Python scripts with their documentation headers."""
        try:
            if not os.path.isdir(DEFAULT_PYTHON_DIR):
                return {"success": False, "message": f"Python directory does not exist: {DEFAULT_PYTHON_DIR}", "scripts": {}}
            
            # Get all ue_ prefixed Python files
            ue_scripts = sorted(f for f in os.listdir(DEFAULT_PYTHON_DIR) if f.startswith('ue_') and f.endswith('.py'))
            
            scripts_info = {}
            
            for script_file in ue_scripts:
                file_path = os.path.join(DEFAULT_PYTHON_DIR, script_file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Extract docstring/header (everything between the first """ and second """)
                    description = ""
                    if content.startswith('"""'):
                        end_idx = content.find('"""', 3)  # Find the closing """
                        if end_idx != -1:
                            description = content[3:end_idx].strip()
                    
                    # Extract key information from the header
                    lines = description.split('\n')
                    title = lines[0] if lines else script_file
                    
                    # Find functionality and usage sections
                    functionality = ""
                    usage = ""
                    parameters = []
                    examples = []
                    
                    current_section = ""
                    for line in lines:
                        line = line.strip()
                        if line.startswith("Functionality:"):
                            current_section = "functionality"
                            continue
                        elif line.startswith("Usage:"):
                            current_section = "usage"
                            continue
                        elif line.startswith("Parameters"):
                            current_section = "parameters"
                            continue
                        elif line.startswith("Examples:"):
                            current_section = "examples"
                            continue
                        elif line.startswith(("Returns:", "Notes:", "Supported", "Output:", "Search", "Camera", "Transform", "Property", "Validation", "LOD", "Use Cases:", "File Management:", "Image Settings:", "Coordinate System:", "Export Process:", "Screenshot Settings:", "Update Behavior:", "Default Behavior:")):
                            current_section = "other"
                            continue
                        
                        if current_section == "functionality" and line:
                            functionality = line
                            current_section = ""  # Only take first line
                        elif current_section == "usage" and line.startswith("MCP Call:"):
                            usage = line.replace("MCP Call: ", "")
                        elif current_section == "parameters" and line.startswith("- ${"):
                            # Extract parameter name and description
                            param_match = line.split(":", 1)
                            if len(param_match) == 2:
                                param_name = param_match[0].replace("- ${", "").replace("}", "").strip()
                                param_desc = param_match[1].strip()
                                parameters.append({"name": param_name, "description": param_desc})
                        elif current_section == "examples" and line.startswith("- {"):
                            examples.append(line[2:])  # Remove "- " prefix
                    
                    scripts_info[script_file] = {
                        "title": title,
                        "functionality": functionality,
                        "usage": usage,
                        "parameters": parameters,
                        "examples": examples[:3],  # Limit to first 3 examples
                        "full_description": description
                    }
                    
                except Exception as e:
                    logger.warning(f"Error reading script {script_file}: {e}")
                    scripts_info[script_file] = {
                        "title": script_file,
                        "functionality": "Error reading file",
                        "usage": "",
                        "parameters": [],
                        "examples": [],
                        "full_description": f"Error: {str(e)}"
                    }
            
            return {
                "success": True, 
                "message": f"Found {len(scripts_info)} UE scripts", 
                "scripts": scripts_info
            }
            
        except Exception as e:
            logger.error(f"Error listing Python scripts: {e}")
            return {"success": False, "message": str(e), "scripts": {}}

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

            script_path = os.path.join(DEFAULT_PYTHON_DIR, "ue_get_camera_0_view_script.py")
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
