import subprocess
from kubernetes import client, config
from qdrant_client import QdrantClient
import ollama

COLLECTION_NAME = "korrupt-logs"
EMBEDDING_MODEL = "nomic-embed-text"

def run_kubectl(command: str) -> dict:
    allowed = ["get", "describe", "logs", "top", "explain"]
    first_word = command.strip().split()[0] if command.strip() else ""
    
    if first_word not in allowed:
        return {
            "success": False,
            "output": f"Command '{first_word}' is not allowed. Only read commands are permitted.",
            "command": command
        }
    
    try:
        result = subprocess.run(
            f"kubectl {command}",
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        return {
            "success": True,
            "output": result.stdout or result.stderr,
            "command": f"kubectl {command}"
        }
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "Command timed out after 30 seconds",
            "command": f"kubectl {command}"
        }
    except Exception as e:
        return {
            "success": False,
            "output": str(e),
            "command": f"kubectl {command}"
        }
        
def get_cluster_overview() -> dict:
    return run_kubectl("get pods -A -o wide")

def describe_pod(pod_name: str, namespace: str = "default") -> dict:
    return run_kubectl(f"describe pod {pod_name} -n {namespace}")

def get_pod_logs(pod_name: str, namespace: str = "default", previous: bool = False) -> dict:
    flag = "--previous" if previous else ""
    return run_kubectl(f"logs {pod_name} -n {namespace} {flag} --tail=100")
    
def get_events(namespace: str = "default") -> dict:
    return run_kubectl(f"get events -n {namespace} --sort-by='.lastTimestamp'")

def search_knowledge_base(query: str, limit: int = 3) -> list[dict]:
    try:
        qdrant = QdrantClient("localhost", port=6333)

        response = ollama.embeddings(
            model=EMBEDDING_MODEL,
            prompt=query
        )
        query_vector = response["embedding"]

        results = qdrant.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            limit=limit
        ).points

        return [
            {
                "score": round(r.score, 4),
                "label": r.payload.get("label"),
                "pod": r.payload.get("pod"),
                "text": r.payload.get("text", "")[:500]
            }
            for r in results
        ]
    except Exception as e:
        return [{"error": str(e)}]