"""
test_mcp_connect.py: connect to the MCP server over ngrok and list its tools.

Prereqs (.env):
  MCP_URL=https://xxxx.ngrok-free.app/mcp
  MCP_AUTH_TOKEN=<the ART_AUTH_TOKEN the server runs with>

  pip install langchain-mcp-adapters python-dotenv

Run (from the tests folder):
  python test_mcp_connect.py
"""

import asyncio
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "Agent"))

from dotenv import load_dotenv
from Clients.mcp import load_mcp_tools

load_dotenv()


async def main():
    tools = await load_mcp_tools()
    print(f"Connected. {len(tools)} tools:\n")
    for t in tools:
        print(f"  {t.name}")
        desc = (t.description or "").splitlines()
        if desc:
            print(f"      {desc[0]}")


if __name__ == "__main__":
    asyncio.run(main())