import os
import torch
from celery import Celery
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
from qdrant_client import QdrantClient

# Import your sandbox function
from app.sandbox import run_code_in_sandbox

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
celery_app = Celery("patchpilot_worker", broker=REDIS_URL, backend=REDIS_URL)

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
qdrant_client = QdrantClient(url=QDRANT_URL)
COLLECTION_NAME = "global_threat_db"

WORKSPACE_DIR = "/workspace"

# Lazy-load variables to save RAM on startup
encoder = None
llm_model = None
llm_tokenizer = None

def load_local_llm():
    """Loads the base model and attaches your custom LoRA weights."""
    global llm_model, llm_tokenizer
    if llm_model is None:
        print("[LLM] Loading Base Model (Qwen 1.5B) and your custom LoRA adapters...")
        
        base_model_id = "Qwen/Qwen2.5-Coder-1.5B"
        # This path must match where you unzipped your folder!
        adapter_path = "/code/fixmaster-lora-v1" 

        llm_tokenizer = AutoTokenizer.from_pretrained(base_model_id)
        
        # Load the base model in float16 to keep RAM usage manageable for Docker
        base_model = AutoModelForCausalLM.from_pretrained(
            base_model_id, 
            torch_dtype=torch.float16, 
            device_map="auto" # Automatically uses GPU if available, else falls back to CPU
        )
        
        # Attach YOUR trained weights!
        llm_model = PeftModel.from_pretrained(base_model, adapter_path)
        print("[LLM] Sovereign AI successfully loaded into memory!")

def retrieve_rag_context(error_logs: str) -> str:
    global encoder
    if encoder is None:
        from sentence_transformers import SentenceTransformer
        encoder = SentenceTransformer("all-MiniLM-L6-v2")
        
    try:
        query_vector = encoder.encode(error_logs[:500]).tolist()
        search_result = qdrant_client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            limit=1 
        )
        
        if search_result:
            best_match = search_result[0].payload
            return f"Remediation Advice: {best_match.get('remediation', 'None')}"
        return "No relevant security context found."
    except Exception:
        return "Warning: RAG Retrieval failed."

def read_workspace_files() -> str:
    workspace_content = ""
    if os.path.exists(WORKSPACE_DIR):
        for root, _, files in os.walk(WORKSPACE_DIR):
            for file in files:
                if file.endswith((".py", ".txt", ".md", ".json")):
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            workspace_content += f"\n--- {file} ---\n{f.read()}\n"
                    except Exception:
                        pass
    return workspace_content or "No readable files found."

def run_ai_agent(error_logs: str):
    print("[Agent] Initializing Local Sovereign Agent...")
    
    rag_context = retrieve_rag_context(error_logs)
    code_context = read_workspace_files()

    # Load your model into memory!
    load_local_llm()
    
    # Format the prompt EXACTLY how we trained it in Colab
    prompt = f"""<|im_start|>system
You are PatchPilot, an autonomous security remediation agent. Given an error log and buggy code, output ONLY the unified Git patch. Do not output conversational text.<|im_end|>
<|im_start|>user
Error: {error_logs}
Code Context: {code_context}
Database Context: {rag_context}<|im_end|>
<|im_start|>assistant
```diff\n"""

    print("[Agent] Generating deterministic Git patch...")
    
    inputs = llm_tokenizer(prompt, return_tensors="pt").to(llm_model.device)
    
    # Generate the patch (temperature=0.1 prevents hallucination)
    outputs = llm_model.generate(
        **inputs, 
        max_new_tokens=256, 
        temperature=0.1,
        pad_token_id=llm_tokenizer.eos_token_id
    )
    
    # Slice the output to only return the newly generated tokens
    input_length = inputs.input_ids.shape[1]
    final_response = llm_tokenizer.decode(outputs[0][input_length:], skip_special_tokens=True)
    
    print("\n=== AI RESPONSE ===")
    print(final_response)
    return final_response

@celery_app.task(bind=True, name="process_github_webhook")
def process_github_webhook(self, repo_name: str, clone_url: str, git_ref: str):
    print(f"[Worker] Initiating pipeline for {repo_name}...")
    
    # Simulating a failed test run
    test_command = "python missing_file.py" 
    sandbox_result = run_code_in_sandbox(repo_url=clone_url, command=test_command)
    
    if not sandbox_result["success"]:
        print(f"[Worker] Build failed! Exit code: {sandbox_result['exit_code']}")
        print("[Worker] Handing logs to AI Agent...")
        ai_patch = run_ai_agent(sandbox_result["logs"])
        return {"status": "patched", "patch": ai_patch}
    
    return {"status": "success"}