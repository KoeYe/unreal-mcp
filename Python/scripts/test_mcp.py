import asyncio
import json
from fastmcp import Client

SERVER_URL = "http://127.0.0.1:9000/sse"

async def call_tool(server_url, tool_name, params):
    """Simple MCP tool caller that handles dict responses"""
    async with Client(server_url) as client:
        try:
            await client.ping()
            result = await client.call_tool(tool_name, params)
            return result
        except Exception as e:
            error_msg = str(e)
            
            # Extract the actual dict response from the error message
            if "input_value=" in error_msg:
                start = error_msg.find("input_value=") + 12
                end = error_msg.find("}", start) + 1
                dict_str = error_msg[start:end]
                
                try:
                    # Parse the dict from the error message
                    import ast
                    actual_response = ast.literal_eval(dict_str)
                    return actual_response
                except:
                    # If parsing fails, return the raw string
                    return {"error": "Parse failed", "raw": dict_str}
            
            return {"error": str(e)}

async def main():
    # Hardcode your tool call here
    tool_name = "api_doc_query"
    params = {"prompt": "convert .obj file into .uassets"}
    
    print(f"Calling {tool_name} with {params}")

    result = await call_tool(SERVER_URL, tool_name, params)
    
    print("\nResult:")
    print(json.dumps(result, indent=2))

    # If it's the expected dict format, extract the actual content
    if isinstance(result, dict):
        if 'success' in result:
            if result['success']:
                print(f"\n✅ Success: {result.get('data', result.get('result', 'No data'))}")
            else:
                print(f"\n❌ Error: {result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    asyncio.run(main())