import os
import json
from mcp import StdioServerParameters, ClientSession
from mcp.client.stdio import stdio_client
from pathlib import Path
mcp_sessions = []
async def load_mcp_config():
    config_path = Path(__file__).parent / "config" / "mcp_config.json"
    with open(config_path) as f:
        return json.load(f)
permission_tool = {
            "name": "get_permission",
            "description": "Get the user's permission reason and action required",
            "input_schema": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Reason of asking permission, e.g. Deleting repo, Removing repo, merging PR",
                    },
                    "action": {
                        "type": "string",
                        "description": "Action as permission required for the reason, e.g. Provide true or false, Write 'I agree to terms'",
                    }
                },

                "required": ["reason", "action"],},
        }
browse_website={
    "name": "browse_website",
    "description": "You browse the website and take the insights and all",
    "input_schema": {
        "type": "object",
        "properties": {
            "task":{
                "type": "string",
                "description": "this is the defined task need to be done, asked by the user. E.g. Can you go on this website photosage.in and find if it toggle button is working or not."
            }
        },
        "required": ["task"]
    }
}
call_permission_tool = {
            "name": "get_call_permission",
            "description": "Get the user's permission by calling them",
            "input_schema": {
                "type": "object",
            }
        }
async def initialize_mcp_clients():
    config = await load_mcp_config()
    all_tools = []
    mcp_lookup = {}
    docker_path = r"C:\Program Files\Docker\Docker\resources\bin\docker.exe"
    i = 0
    for server_name, server_config in config["mcpServers"].items():
        command = server_config["command"]
        # Use docker path if command is docker
        if command == "docker":
            if not os.path.exists(docker_path):
                print(f"Docker not found for {server_name}, skipping...")
                continue
            command = docker_path

        params = StdioServerParameters(
            command=command,
            args=server_config["args"],
            env=server_config["env"] if "env" in server_config else None
        )

        try:
            # session = await stdio_client(params)
            # tools = await session.list_tools()
            #
            # for tool in tools:
            #     curr_tool = {
            #         "name": tool.name,
            #         "description": tool.description,
            #         "input_schema": tool.inputSchema,
            #     }
            #     all_tools.append(curr_tool)
            #     mcp_lookup[tool.name] = [server_name, session]
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    for tool in tools.tools:
                        curr_tool = {
                            "name": tool.name,
                            "description": tool.description,
                            "input_schema": tool.inputSchema,
                        }
                        print(f"Current tool:{i}", tool.name)
                        i = i+1

                        if tool.name in mcp_lookup:
                            print("Looking up tool Duplicate", tool.name)
                        else:
                            all_tools.append(curr_tool)
                            mcp_lookup[tool.name] = [server_name, (params)]

        except Exception as e:
            print(f"Failed to initialize {server_name}: {e}")
    all_tools.append(permission_tool)
    all_tools.append(call_permission_tool)
    all_tools.append(browse_website)
    return all_tools, mcp_lookup

