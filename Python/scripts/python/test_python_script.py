import sys
import os
import time
import socket
import json
import logging
from typing import Dict, Any, Optional

# Add the parent directory to the path so we can import the server module
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TestPhysicsVariables")

def send_command(sock: socket.socket, command: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Send a command to the Unreal MCP server and get the response."""
    try:
        # Create command object
        command_obj = {
            "type": command,
            "params": params
        }

        # Convert to JSON and send
        command_json = json.dumps(command_obj)
        logger.info(f"Sending command: {command_json}")
        sock.sendall(command_json.encode('utf-8'))

        # Receive response
        chunks = []
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)

            # Try parsing to see if we have a complete response
            try:
                data = b''.join(chunks)
                json.loads(data.decode('utf-8'))
                # If we can parse it, we have the complete response
                break
            except json.JSONDecodeError:
                # Not a complete JSON object yet, continue receiving
                continue

        # Parse response
        data = b''.join(chunks)
        response = json.loads(data.decode('utf-8'))
        logger.info(f"Received response: {response}")
        return response

    except Exception as e:
        logger.error(f"Error sending command: {e}")
        return None


def main():
    """Main function to test physics variables in blueprints."""
    try:
        # Step 1: Create blueprint for a physics-based obstacle
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("127.0.0.1", 55557))
        print("Connected to Unreal MCP server")
#         python_script = """import unreal

# print("Hello from Unreal Python!")

# unreal.log("Creating a physics-based obstacle blueprint")
# """
#         print("sending script to create blueprint")
#         response = send_command(sock, "execute_python_script", {"script": python_script, "path": None})
#         if not response or not response.get("success"):
#             logger.error("Failed to execute Python script in Unreal Engine")

        python_script_path = "D:\\Playground\\unreal_mcp\\Python\\scripts\\python\\test_script.py"

        print("sending script path to create blueprint")
        response = send_command(sock, "execute_python_script", {"script": None, "path": python_script_path})
        if not response or not response.get("success"):
            logger.error("Failed to execute Python script in Unreal Engine")
        return

    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
    finally:
        sock.close()

if __name__ == "__main__":
    main()