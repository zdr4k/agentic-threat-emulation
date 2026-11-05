
import os

from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv()


async def load_mcp_tools():
    """Connect to the Atomic Red Team MCP server."""

    url = os.environ["MCP_URL"]
    token = os.environ["MCP_AUTH_TOKEN"]

    client = MultiServerMCPClient({
        "atomic_red_team": {
            "url": url,
            "transport": "streamable_http",
            "headers": {
                "Authorization": f"Bearer {token}"
            }
        }
    })

    return await client.get_tools()
