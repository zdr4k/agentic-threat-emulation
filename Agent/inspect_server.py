
import asyncio
import json

from Clients.mcp import load_mcp_tools


async def main():
    tools = {
        tool.name: tool
        for tool in await load_mcp_tools()
    }

    server_info = tools.get("server_info")

    if server_info is None:
        raise RuntimeError("server_info is unavailable")

    result = await server_info.ainvoke({})

    print(
        json.dumps(
            result,
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
