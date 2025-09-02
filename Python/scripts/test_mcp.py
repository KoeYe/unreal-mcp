import asyncio
import json
from fastmcp import Client
from fastmcp.exceptions import ToolError

SERVER_URL = "http://127.0.0.1:9000/sse"

async def main():
    async with Client(SERVER_URL) as client:
        tool_name = "api_doc_query"
        params = {
            "query": "What Python API functions should I use to capture screenshots from a specific camera actor in Unreal Engine?"
        }
        print(f"Calling {tool_name} with:\n{params}\n")

        try:
            result = await client.call_tool(tool_name, params, raise_on_error=False)
        except ToolError as e:
            print(f"CallTool error: {e}")
            return

        # 是不是调用错误？
        if result.is_error:
            print("❌ Tool execution failed.")
            if result.content:
                print("Text Content Error Message:")
                for content in result.content:
                    print(content.text)
            return

        # 优先使用 structured_content 获取结构化输出
        if result.structured_content is not None:
            print("✅ Structured Content (original dict you returned):")
            print(json.dumps(result.structured_content, indent=2, ensure_ascii=False))
        else:
            print("ℹ No structured content available.")

        # 永远可以读取 content 中的文本块
        if result.content:
            print("\n--- Text Content Blocks: ---")
            for content in result.content:
                print(content.text)

        # 如果你想进一步使用 .data（注意可能是自定义类型，非 JSON 序列化型）
        if result.data is not None:
            print("\n=== Hydrated `.data` object: ===")
            print(result.data)

if __name__ == "__main__":
    asyncio.run(main())
