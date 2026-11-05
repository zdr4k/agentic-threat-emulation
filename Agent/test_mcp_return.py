
import asyncio
from Clients.mcp import load_mcp_tools


async def main():
    tools = await load_mcp_tools()

    for tool in tools:
        print(f"\nTool: {tool.name}")
        print(f"Description: {tool.description}")
        print(f"Arguments: {tool.args_schema}")


if __name__ == "__main__":
    asyncio.run(main())
