"""
mcp.py: connects to the Atomic Red Team MCP server and exposes its tools
(query_atomics, execute_atomic, server_info, ...) as LangChain tools.

The server runs on the lab VM with execution enabled, reached over an ngrok
tunnel. URL and bearer token come from the environment:
  MCP_URL          e.g. https://xxxx.ngrok-free.app/mcp
  MCP_AUTH_TOKEN   the ART_AUTH_TOKEN the server was started with
"""

from __future__ import annotations

import os

from langchain_mcp_adapters.client import MultiServerMCPClient


def _config() -> dict:
    url = os.environ["MCP_URL"]
    token = os.environ["MCP_AUTH_TOKEN"]
    return {
        "atomic": {
            "transport": "streamable_http",
            "url": url,
            "headers": {
                "Authorization": f"Bearer {token}",
                # ngrok free interstitial page; skip it for API calls.
                "ngrok-skip-browser-warning": "true",
            },
        }
    }


async def load_mcp_tools() -> list:
    """Connect to the MCP server and return its tools as LangChain tools."""
    client = MultiServerMCPClient(_config())
    return await client.get_tools()
