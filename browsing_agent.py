from langchain_google_genai import ChatGoogleGenerativeAI
from browser_use import Agent, BrowserConfig, Browser
from dotenv import load_dotenv
import re
import asyncio

load_dotenv()

# Initialize browser and LLM only once globally
browser = Browser(
    config=BrowserConfig(
        chrome_instance_path='C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
    )
)
llm = ChatGoogleGenerativeAI(model='gemini-2.0-flash-exp')

async def _run_agent_and_extract(task: str):
    agent = Agent(
        task=(
            task
        ),
        llm=llm,
    )
    result = await agent.run()

    # Regex to extract desired content
    pattern = r"ActionResult\([^)]*success=True[^)]*extracted_content='([^']*)'"
    match = re.search(pattern, str(result))

    if match:
        return match.group(1)
    else:
        return None

def run_browser_task_and_get_result(task: str):
    try:
        extracted_content = asyncio.run(_run_agent_and_extract(task))
        return extracted_content
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

# Example usage:

