import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools as load_tools

load_dotenv()


def create_mcp_client():
    return MultiServerMCPClient({
        "atomic_red_team": {
            "url": os.environ["MCP_URL"],
            "transport": "streamable_http",
            "headers": {
                "Authorization": f"Bearer {os.environ['MCP_AUTH_TOKEN']}"
            }
        }
    })


async def load_mcp_tools():
    client = create_mcp_client()
    return await client.get_tools()


@asynccontextmanager
async def mcp_session():
    client = create_mcp_client()

    async with client.session("atomic_red_team") as session:
        tools = await load_tools(session)
        yield {tool.name: tool for tool in tools}