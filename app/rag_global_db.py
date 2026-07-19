import os
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer

# Connect to the local Qdrant container
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
client = QdrantClient(url=QDRANT_URL)

COLLECTION_NAME = "global_threat_db"

# lightweight, local open-source embedding model
print("Loading local embedding model (all-MiniLM-L6-v2)...")
encoder = SentenceTransformer("all-MiniLM-L6-v2")

def initialize_db():
    print(f"Connecting to Qdrant at {QDRANT_URL}...")
    
    # Create the collection if it doesn't exist
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=encoder.get_sentence_embedding_dimension(), 
                distance=Distance.COSINE
            ),
        )
        print(f"Collection '{COLLECTION_NAME}' created successfully.")
    else:
        print(f"Collection '{COLLECTION_NAME}' already exists.")

def seed_threat_data():
    """
    initial dataset
    """
    threats = [
        {
            "id": 1,
            "vuln_type": "SQL Injection (SQLi)",
            "description": "Occurs when untrusted user input is directly concatenated into a database SQL query, allowing attackers to manipulate the query.",
            "remediation": "Always use parameterized queries or Prepared Statements. Never use string formatting (e.g., f-strings in Python) to build SQL queries."
        },
        {
            "id": 2,
            "vuln_type": "Cross-Site Scripting (XSS)",
            "description": "Occurs when an application includes untrusted data in a web page without proper validation or escaping.",
            "remediation": "Use context-aware output encoding. In modern frameworks like React, this is handled automatically, but avoid using 'dangerouslySetInnerHTML'."
        },
        {
            "id": 3,
            "vuln_type": "Directory Traversal",
            "description": "Allows an attacker to read arbitrary files on the server by using '../' sequences in file path inputs.",
            "remediation": "Resolve all paths to their absolute paths using os.path.abspath(), and verify the resolved path starts with the expected base directory."
        },
        {
            "id": 4,
            "vuln_type": "Hardcoded Secrets",
            "description": "API keys, passwords, or tokens are committed directly into the source code.",
            "remediation": "Use environment variables (os.getenv) or a secure secret manager (like AWS Secrets Manager or HashiCorp Vault)."
        }
    ]

    print("Generating vector embeddings for threat data...")
    points = []
    for threat in threats:
        # We embed the description and vulnerability type so the AI can search by concepts
        text_to_embed = f"Vulnerability: {threat['vuln_type']}. Description: {threat['description']}"
        vector = encoder.encode(text_to_embed).tolist()
        
        points.append(
            PointStruct(
                id=threat["id"],
                vector=vector,
                payload={
                    "vuln_type": threat["vuln_type"],
                    "remediation": threat["remediation"]
                }
            )
        )
    
    # Upload to Qdrant
    client.upsert(
        collection_name=COLLECTION_NAME,
        points=points
    )
    print(f"Successfully seeded {len(threats)} threat profiles into Qdrant!")

if __name__ == "__main__":
    initialize_db()
    seed_threat_data()