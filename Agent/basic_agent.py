"""
basic_agent.py: minimal agent, one tool, the core tool-calling loop.

Run (from the Agent folder):
  python basic_agent.py
Needs OPENAI_API_KEY in a .env file.
"""

import os
import sys

# Make the Agent folder importable so "from Tools..." works when run directly.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from Tools.read_rule import read_rule

load_dotenv()

TOOLS = [read_rule]
TOOLS_BY_NAME = {t.name: t for t in TOOLS}


def build_model():
    return ChatOpenAI(model="gpt-4o-mini", temperature=0.1)


def run(question: str) -> str:
    model = build_model().bind_tools(TOOLS)

    messages = [
        SystemMessage(content=(
            "You are a detection engineering assistant. When asked about a "
            "detection rule, use the read_rule tool, then answer from what it "
            "returns."
        )),
        HumanMessage(content=question),
    ]

    ai = model.invoke(messages)
    messages.append(ai)

    # The loop: while the model wants tools, run them and feed results back.
    while ai.tool_calls:
        for call in ai.tool_calls:
            print(f"  -> model called {call['name']}({call['args']})")
            result = TOOLS_BY_NAME[call["name"]].invoke(call["args"])
            messages.append(ToolMessage(content=str(result),
                                        tool_call_id=call["id"]))
        ai = model.invoke(messages)
        messages.append(ai)

    return ai.content


if __name__ == "__main__":
    q = ("What ATT&CK technique does the rule powershell_encoded_command.yml "
         "claim to cover, and what table does it read?")
    print(f"Q: {q}\n")
    print(f"\nA: {run(q)}")
