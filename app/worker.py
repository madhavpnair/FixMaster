import os
import asyncio
from celery import Celery
from app.sandbox import run_code_in_sandbox


# LangChain and MCP Imports
from langchain_core.messages import HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_google_genai import ChatGoogleGenerativeAI 


# Pull connection string from docker-compose.yml
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Initialize Celery
celery_app = Celery("fixmaster_worker", broker=REDIS_URL, backend=REDIS_URL)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


async def run_ai_agent(error_logs: str):
    """
    Starts the MCP Client, connects to our MCP Server, and asks the LLM to fix the bug.
    """
    print("[Agent] Connecting to MCP Server...")
    
    # Configure the MCP Client to start our local server via standard input/output
    mcp_config = {
        "repo_tools": {
            "command": "python",
            "args": ["app/mcp_server.py"], # This points to the file we just created
            "transport": "stdio",
        }
    }
    

    client = MultiServerMCPClient(mcp_config)
    print("[Agent] Fetching tools from MCP Server...")
    tools = await client.get_tools()
        
    # Initialize the LLM (You will need to set OPENAI_API_KEY or use a local model)
    # Note: We are using a fast model here for testing.
    llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash-latest",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            api_version="v1",
            temperature=0
        )
    
    # Bind tools to the model
    # llm_with_tools = llm.bind_tools(tools)

    # 2. Define the System Prompt to give the AI "tools" via instructions
    system_prompt = """
    You are an AI SRE. You have access to these tools:
    - list_directory(path: str): Lists files.
    - read_file(filepath: str): Reads content of a file.
    
    The user will provide a build error log. You must investigate the repo to find the issue.
    Explain the bug and provide the fix.
    """
    
    # 3. Analyze logs
    prompt = f"{system_prompt}\n\nBuild failure logs:\n{error_logs}\n\nWhat is the bug?"
    
    # 4. Invoke LLM
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    

    # print(f"DEBUG: API Key exists: {bool(os.getenv('GOOGLE_API_KEY'))}")
    
    
    # Create the LangGraph agent equipped with our MCP tools
    # agent = create_react_agent(llm_with_tools, tools)
    
    # print("[Agent] Analyzing error logs...")
    # prompt = f"""
    # A build failure occurred in our repository. 
    # Here are the compiler/execution logs:
    
    # <logs>
    # {error_logs}
    # </logs>
    
    # Please use your tools to investigate the repository files, find the bug, and provide a unified git diff (.patch format) to fix it.
    # """
    
    # # Invoke the agent!
    # response = await agent.ainvoke({"messages": [("user", prompt)]})
    
    print("\n=== AI RESPONSE ===")
    print(response["messages"][-1].content)
    print("===================\n")
    
    return response["messages"][-1].content

@celery_app.task(bind=True, name="process_github_webhook")
def process_github_webhook(self, repo_name: str, clone_url: str, git_ref: str):
    print(f"[Worker] Initiating pipeline for {repo_name}...")
    
    # --- PHASE 1: THE SANDBOX ---
    test_command = "python missing_file.py" 
    
    print(f"[Worker] Sending code to isolated sandbox...")
    sandbox_result = run_code_in_sandbox(repo_url=clone_url, command=test_command)
    
    if sandbox_result["success"]:
        print("[Worker] Code executed perfectly! No AI patch needed.")
        return {"status": "success", "repo": repo_name}
    else:
        print(f"[Worker] Build failed! Exit code: {sandbox_result['exit_code']}")
        print(f"[Worker] Handing logs to AI Agent via MCP...")
        
        # --- PHASE 2: MCP & LLM Agent ---
        # Since Celery runs synchronous tasks, we need to run our async LangChain agent like this:
        try:
            # Note: This requires an OPENAI_API_KEY environment variable to work!
            loop = asyncio.get_event_loop()
            ai_patch = loop.run_until_complete(run_ai_agent(sandbox_result["logs"]))
            
            return {"status": "patched", "repo": repo_name, "patch": ai_patch}
            
        except Exception as e:
            print(f"[Worker] Agent failed: {str(e)}")
            return {"status": "error", "repo": repo_name, "error": str(e)}