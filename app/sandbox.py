import docker
import os

def run_code_in_sandbox(repo_url: str, command: str) -> dict:
    """
    This function spins up a temporary Docker container, clones the code,
    runs a command (like a test or linter), and captures the output.
    """
    try:
        # Connect to the DinD (Docker-in-Docker) service.
        client = docker.from_env()
        
        print(f"[Sandbox] Connected to Docker engine. Starting isolated container...")

        # Define the bash script that will run INSIDE the temporary container
        # debugged the git not found issue
        bash_script = f"""
        apt-get update && apt-get install -y git   
        git clone {repo_url} /workspace
        cd /workspace
        {command}
        """

        # Run the container
        # mounted the shared /workspace volume so the worker can read the files later
        container = client.containers.run(
            image="python:3.11", 
            command=["/bin/sh", "-c", bash_script],
            volumes={'/workspace': {'bind': '/workspace', 'mode': 'rw'}},
            detach=True,                            
            remove=False,                           
            network_mode="bridge"                   
        )

        # Wait for the container to finish running the code
        result = container.wait()
        exit_code = result['StatusCode'] # 0 for success

        # Grab the output (the stdout/stderr logs)
        logs = container.logs().decode('utf-8')
        
        # Clean up: destroy the temporary container
        container.remove()

        print(f"[Sandbox] Execution finished with exit code {exit_code}")
        
        return {
            "exit_code": exit_code,
            "logs": logs,
            "success": exit_code == 0
        }

    except Exception as e:
        print(f"[Sandbox] CRITICAL ERROR: {str(e)}")
        return {
            "exit_code": -1,
            "logs": f"Sandbox failed to execute: {str(e)}",
            "success": False
        }