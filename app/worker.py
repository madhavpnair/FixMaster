import os
from celery import Celery
from app.sandbox import run_code_in_sandbox

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

@celery_app.task(bind=True, name="process_github_webhook")
def process_github_webhook(self, repo_name: str, clone_url: str, git_ref: str):
    """
    This task is triggered by FastAPI. It handles the heavy lifting.
    """
    print(f"[Worker] Initiating pipeline for {repo_name}...")
    
    # --- PHASE 1: THE SANDBOX ---
    # We will simulate running a linter (flake8) to look for code errors.
    # Since we are using a dummy repo, we will just run 'ls -la' to prove it cloned successfully,
    # and then run a command that we KNOW will fail (like trying to run a python script that doesn't exist)
    # so we can see how the system captures errors!
    
    test_command = "ls -la && python missing_file.py" 
    
    print(f"[Worker] Sending code to isolated sandbox...")
    sandbox_result = run_code_in_sandbox(repo_url=clone_url, command=test_command)
    
    if sandbox_result["success"]:
        print("[Worker] Code executed perfectly! No AI patch needed.")
    else:
        print(f"[Worker] Build failed! Exit code: {sandbox_result['exit_code']}")
        print(f"[Worker] Capturing Error Logs for the AI:\n{sandbox_result['logs']}")
        
        # --- PHASE 2 PREVIEW ---
        # This is where we will eventually pass 'sandbox_result["logs"]' 
        # to our MCP-enabled LLM to figure out how to fix the error!
        print("[Worker] (Future) Handing logs to AI Agent via MCP...")

    return {"status": "completed", "repo": repo_name}