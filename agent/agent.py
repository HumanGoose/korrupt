import os
import anthropic
from dotenv import load_dotenv
from agent.tools import (
    get_cluster_overview,
    describe_pod,
    get_pod_logs,
    get_events,
    search_knowledge_base
)
from agent.prompts import SYSTEM_PROMPT, TOOL_DESCRIPTIONS

load_dotenv()

TOOL_MAP = {
    "get_cluster_overview": get_cluster_overview,
    "describe_pod": describe_pod,
    "get_pod_logs": get_pod_logs,
    "get_events": get_events,
    "search_knowledge_base": search_knowledge_base
}

def execute_tool(tool_name: str, tool_input: dict) -> str:
    """Execute a tool and return its output as a string."""
    if tool_name not in TOOL_MAP:
        return f"Unknown tool: {tool_name}"

    func = TOOL_MAP[tool_name]
    result = func(**tool_input)

    if isinstance(result, list):
        return str(result)
    if isinstance(result, dict):
        return result.get("output", str(result))
    return str(result)

def run_agent(
    user_message: str,
    on_tool_call=None,
    on_tool_result=None
) -> str:
    """
    Run the Korrupt agent loop.

    on_tool_call: callback fired when agent calls a tool
                  receives (tool_name, tool_input)
    on_tool_result: callback fired when tool returns
                    receives (tool_name, result)
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set in .env")

    client = anthropic.Anthropic(api_key=api_key)

    messages = [
        {"role": "user", "content": user_message}
    ]

    while True:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOL_DESCRIPTIONS,
            messages=messages
        )

        # Add assistant response to message history
        messages.append({
            "role": "assistant",
            "content": response.content
        })

        # If model is done — return the final text
        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return "No response generated"

        # If model wants to use tools
        if response.stop_reason == "tool_use":
            tool_results = []

            for block in response.content:
                if block.type != "tool_use":
                    continue

                tool_name = block.name
                tool_input = block.input

                # Fire callback so UI can show what's happening
                if on_tool_call:
                    on_tool_call(tool_name, tool_input)

                # Actually execute the tool
                result = execute_tool(tool_name, tool_input)

                # Fire callback so UI can show the result
                if on_tool_result:
                    on_tool_result(tool_name, result)

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result
                })

            # Send tool results back to the model
            messages.append({
                "role": "user",
                "content": tool_results
            })

if __name__ == "__main__":
    def on_tool_call(name, inputs):
        print(f"\n🔧 Calling: {name}({inputs})")

    def on_tool_result(name, result):
        print(f"✓ {name} returned {len(str(result))} chars")

    response = run_agent(
        "My cluster has issues, investigate all unhealthy pods and tell me exactly what is wrong and how to fix it",
        on_tool_call=on_tool_call,
        on_tool_result=on_tool_result
    )

    print("\n" + "="*60)
    print(response)