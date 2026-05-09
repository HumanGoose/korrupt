import ollama
from qdrant_client import QdrantClient

COLLECTION_NAME = "korrupt-logs"
EMBEDDING_MODEL = "nomic-embed-text"

def search(query: str, limit: int = 3):
    client = QdrantClient("localhost", port=6333)

    # Embed the query
    response = ollama.embeddings(
        model=EMBEDDING_MODEL,
        prompt=query
    )
    query_vector = response["embedding"]

    # Search Qdrant
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=limit
    ).points

    print(f"\nQuery: '{query}'")
    print("=" * 60)

    for i, result in enumerate(results):
        print(f"\nResult {i+1} — Score: {result.score:.4f}")
        print(f"Label: {result.payload['label']}")
        print(f"Pod: {result.payload['pod']}")
        print(f"Source: {result.payload['source_file']}")

if __name__ == "__main__":
    search("pod ran out of memory and keeps restarting")
    search("container keeps crashing with error")
    search("healthy cluster no issues")