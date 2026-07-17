from fastapi import FastAPI, Request
from app.worker import process_github_webhook

app = FastAPI(title="DiffGuardian API Gateway")

@app.get("/health")
def health_check():
    return {"status": "ok", "engine": "DiffGuardian CI/CD System"}

@app.post("/webhook")
async def github_webhook(request: Request):
    payload = await request.json()
    
    # Extract git reference and repository name
    repo_name = payload.get("repository", {}).get("full_name", "Unknown Repo")
    ref = payload.get("ref", "refs/heads/main")
    
    print(f"[API Gateway] Webhook received. Handing off {repo_name} to task queue...")
    
    # .delay() is the magic Celery method that sends the task to Redis
    # without blocking the FastAPI response.
    task = process_github_webhook.delay(repo_name, payload.get("repository", {}).get("clone_url", ""), ref)
    
    return {
        "message": "Payload accepted. Pipeline initiated in background.",
        "task_id": task.id
    }