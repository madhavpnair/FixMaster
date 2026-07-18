import os
from mcp.server.fastmcp import FastMCP

# server that can be connected to llm
mcp = FastMCP("FixMaster-Repo-Tools")

# AI is restricted to the /workspace directory.
WORKSPACE_DIR = "/workspace"

@mcp.tool()
def read_file(filepath: str) -> str:
    """
    Reads the content of a file in the repository.
    The AI will use this when it sees an error in a specific file and needs to look at the code.
    """
    print(f"[MCP Server] AI requested to read file: {filepath}")
    
    # Security check: Prevent directory traversal attacks (e.g., passing "../../etc/passwd")
    safe_path = os.path.abspath(os.path.join(WORKSPACE_DIR, filepath))
    if not safe_path.startswith(WORKSPACE_DIR):
        return "Error: Access Denied. You can only read files inside the repository."
    
    try:
        with open(safe_path, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        return f"Error: The file '{filepath}' does not exist."
    except Exception as e:
        return f"Error reading file: {str(e)}"

@mcp.tool()
def list_directory(path: str = ".") -> str:
    """
    Lists all files and folders in a given directory.
    The AI uses this to understand the structure of the repository.
    """
    print(f"[MCP Server] AI requested to list directory: {path}")
    
    safe_path = os.path.abspath(os.path.join(WORKSPACE_DIR, path))
    if not safe_path.startswith(WORKSPACE_DIR):
        return "Error: Access Denied."
        
    try:
        items = os.listdir(safe_path)
        return "\n".join(items) if items else "Directory is empty."
    except FileNotFoundError:
        return f"Error: The directory '{path}' does not exist."
    except Exception as e:
        return f"Error listing directory: {str(e)}"

if __name__ == "__main__":
    # When run directly, this starts the server listening for requests from the AI Agent
    print("[MCP Server] Starting up. Awaiting Agent connections...")
    # LangChain will use stdio
    mcp.run(transport="stdio")