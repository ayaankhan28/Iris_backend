import asyncio
import json
import os
import requests
from mcp import StdioServerParameters, ClientSession
from mcp.client.stdio import stdio_client
from anthropic import Anthropic
from dotenv import load_dotenv
from typing import  Optional
from browsing_agent import run_browser_task_and_get_result,_run_agent_and_extract
from pprint import pprint
from constants import *
# Load environment variables
load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_ACCESS_TOKEN")
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



async def surf_website(task):
    try:
        final_result = await _run_agent_and_extract(task)
        if final_result is not None:
            return final_result
        return "No results found for the website"
    except Exception as e:
        return "Not able to run browser task"




def update_tool_input_with_sha(tool_name, tool_input):
    keys = ["path", "file_path", "filepath", "filePath"]
    for key in keys:
        if key in tool_input:
            sha = get_github_file_sha(f'{tool_input["owner"]}/{tool_input["repo"]}', tool_input[key])
            if sha:
                tool_input["sha"] = sha
            break
    return tool_input
def ask_user_permission():
    while True:
        response = input(f"\nPermission Required: Do you grant permission? (yes/no): ").strip().lower()
        if response in ["yes", "y"]:
            return True
        elif response in ["no", "n"]:
            return False
        else:
            print("Invalid input. Please enter 'yes' or 'no'.")
# --- Call a tool ---
async def call_tool_async(session1, tool_name, inputs):
    print("Actual tool call started------------------------------------------")
    print(f"\n🔧 Calling Tool: {tool_name}")
    print("Inputs",inputs)
    print("Session",session1)
    print("SEssion Type,",type(session1))
    if tool_name == "get_permission":
        permit = ask_user_permission()
        return "permission Status: User response"+str(permit)

    inputs = update_tool_input_with_sha(tool_name, inputs)
    print('INputs New',inputs)
    try:
        print("Bismillah")
        async with stdio_client(session1) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                result = await session.call_tool(tool_name, inputs)
                print("Result",result)

                result_text = result.content[0].text if result.content else ""
                print("Result TExt",result_text)
                print(f"✅ Tool Result:")
                pprint(result_text)
                print("Actual tool call ended------------------------------------------")
                return result_text
    except Exception as e:
        print("found error",e)
        return  None


# --- Main Claude task processor (multi-tool supported) ---
async def process_task(handle_outbound_logic, anthropic, session, query, available_tools, broadcast_message, task_id: Optional[str]=None):

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
        try:
            response = anthropic.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                messages=messages,
                system="You are Iris the Full stack  software engineer 1 with high knowleage of every domain at the company photosage. and always generate the content in beautiful markdown . ALWAYS INTRODUCE YOURSLEF UNDER 20 WORDS AS 'Hi this is Iris' and greet user with their name",
                tools=available_tools,
            )
        except Exception as e:
            print("error",e)

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
                    await broadcast_message(f"Connecting to {session[content.name][0]}")
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
            await broadcast_message(f"Using tool: {session[tool_name][0]}: {tool_name}")
            tool_args = tool_call.input
            print("Tool args is", tool_args)
            if a==1:
                # await broadcast_message(f"*Github Repo*: ```{tool_args["owner"]}``` , ```{tool_args["repo"]}```")
                await wait()

            if tool_name=="get_call_permission":
                transcript = await handle_outbound_logic(messages)
                await broadcast_message(
                    message=transcript,
                    type="status"
                )
                print("TRANSCRIPT", transcript)
                result = "User permission : "+transcript
            elif tool_name=="get_permission":
                result = await broadcast_message(message=tool_args["action"], type="permission",title=tool_args["reason"])

            elif tool_name=="browse_website":

                result = await surf_website(tool_args["task"])
                await broadcast_message(message=result)
            else:
                result = await call_tool_async(session[tool_name][1], tool_name, tool_args)
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


async def main(user_query, broadcast_message, handle_outbound_logic,mcp_tools: [],mcp_lookup: {}):

    anthropic = Anthropic(api_key=ANTHROPIC_API_KEY)

    # pprint(mcp_tools)
    result = await process_task(
        handle_outbound_logic,
        anthropic,
        mcp_lookup,  # Using first session; adjust if process_task needs multiple sessions
        user_query,
        mcp_tools,
        broadcast_message
    )
    result = "hi"
    print("\n🧠 Final Response:\n", result)

    # await broadcast_message("Hi there this is working")
    # codeChange = [
    #     {
    #         "filename": "database.py",
    #         "oldCode": oldCode,
    #         "newCode": newCode
    #
    #     },
    #     {
    #         "oldCode": oldCode1,
    #         "newCode": newCode1,
    #         "filename": "main.py"
    #     }
    #
    # ]
    # await broadcast_message(type="code_viewer",codeChange=codeChange)
    # result = "hi"
    """
import asyncio
import json
import os
import requests    
    """
    return result