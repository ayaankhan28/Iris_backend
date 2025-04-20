import asyncio
import json
import os
import requests
from mcp import StdioServerParameters, ClientSession
from mcp.client.stdio import stdio_client
from anthropic import Anthropic
from dotenv import load_dotenv
from typing import  Optional

from pprint import pprint

# Load environment variables
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
ANTHROPIC_API_KEY = os.getenv("CLAUDE_KEY")
MCP_GITHUB_PAT =GITHUB_TOKEN
async def wait(sec: Optional[int] = 1):
    await asyncio.sleep(sec)
# --- Optional GitHub SHA helper ---
def get_github_file_sha(repo: str, path: str):
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get("sha")
    return None

def update_tool_input_with_sha(tool_name, tool_input):
    keys = ["path", "file_path", "filepath", "filePath"]
    for key in keys:
        if key in tool_input:
            sha = get_github_file_sha(f'{tool_input["owner"]}/{tool_input["repo"]}', tool_input[key])
            if sha:
                tool_input["sha"] = sha
            break
    return tool_input

# --- Call a tool ---
async def call_tool_async(session, tool_name, inputs):
    print(f"\n🔧 Calling Tool: {tool_name}")
    inputs = update_tool_input_with_sha(tool_name, inputs)
    try:
        result = await session.call_tool(tool_name, inputs)

        result_text = result.content[0].text if result.content else ""
        print(f"✅ Tool Result:")
        pprint(result_text)
        return result_text
    except Exception as e:
        print("found error",e)
        return  None


# --- Main Claude task processor (multi-tool supported) ---
async def process_task(anthropic, session, query, available_tools, broadcast_message, task_id: Optional[str]=None):
    messages = [{"role": "user", "content": query}]
    final_response = []

    print("🚀 Starting Task...")
    a = 1
    await wait()
    task_id = await broadcast_message(message="we have to add your own tools",type="task",title="Add your own tools",progress="todo")
    while True:
        # Get model response
        print("Message aboout to send to the claude")
        pprint(messages)
        response = anthropic.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1000,
            messages=messages,
            system="You are alex the Full stack  software engineer 1 with high knowleage of every domain at the company photosage. and always generate the content in beautiful markdown . ALWAYS INTRODUCE YOURSLEF UNDER 20 WORDS AS 'Hi this is Alex' and greet user with their name",
            tools=available_tools,
        )

        # Track current message's content
        assistant_content = []
        tool_calls = []
        print(f"Response {a}",response)

        for content in response.content:
            if content.type == "text":
                print("--------------------")
                print("Assistant response without tool use", content.text)
                print("--------------------")
                await broadcast_message(content.text)
                final_response.append(content.text)
                assistant_content.append({"type": "text", "text": content.text})
            elif content.type == "tool_use":
                if a==1:
                    await broadcast_message("Connecting to Github")
                    await wait()
                tool_calls.append(content)

        if not tool_calls:
            # No tools left — task is complete

            print("\n✅ All tools executed. Task completed.")
            break

        # Add current assistant response to conversation

        print(f"Required Tools for this run {a}")
        pprint(tool_calls)
        # For each tool, execute & return result
        for tool_call in tool_calls:
            print("Tool call started")
            pprint(tool_call)
            tool_name = tool_call.name
            print("Tool name is", tool_name)
            await broadcast_message(f"Using tool: {tool_name}")
            tool_args = tool_call.input
            print("Tool args is", tool_args)
            if a==1:
                await broadcast_message(f"*Github Repo*: ```{tool_args["owner"]}``` , ```{tool_args["repo"]}```")
                await wait()


            result = await call_tool_async(session, tool_name, tool_args)
            if not result:
                print("error occured")
                break

            # Add tool result to the conversation
            assistant_content.append({
                "type": "tool_use",
                "name": tool_name,
                "input": tool_args,
                "id": tool_call.id
            })
            print("Assistant tool message")
            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": tool_call.id, "content": result}]
            })
            a = a + 1

    return "\n".join(final_response)

# --- Entry point ---
async def main(user_query, broadcast_message):


    docker_path = r"C:\Program Files\Docker\Docker\resources\bin\docker.exe"
    if not os.path.exists(docker_path):
        raise FileNotFoundError("Docker not found.")

    anthropic = Anthropic(api_key=ANTHROPIC_API_KEY)

    server_params = StdioServerParameters(
        command=docker_path,
        args=[
            "run",
            "-i",
            "--rm",
            "-e", f"GITHUB_PERSONAL_ACCESS_TOKEN={MCP_GITHUB_PAT}",
            "ghcr.io/github/github-mcp-server"
        ]
    )

    user_input = user_query

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tool_response = await session.list_tools()

            available_tools = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema,
                }
                for tool in tool_response.tools
            ]

            print(f"\n🛠️ Tools available: {[t['name'] for t in available_tools]}")


            result = await process_task(anthropic, session, user_input, available_tools,broadcast_message)
            result = "testing"
            print("\n🧠 Final Response:\n", result)
            return result


