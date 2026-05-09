import uuid
import ollama
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from rich.console import Console
from rich.progress import track

from chunker import chunk_all_collections

console = Console()

COLLECTION_NAME = "korrupt-logs"
EMBEDDING_MODEL = "nomic-embed-text"
VECTOR_SIZE = 768  # nomic-embed-text produces 768-dimensional vectors

def get_embedding(text: str) -> list[float]:
    response = ollama.embeddings(
        model=EMBEDDING_MODEL,
        prompt=text
    )
    return response["embedding"]

def setup_collection(client: QdrantClient):
    """Create the Qdrant collection if it doesn't exist."""
    existing = [c.name for c in client.get_collections().collections]
    
    if COLLECTION_NAME in existing:
        console.print(f"[yellow]Collection '{COLLECTION_NAME}' already exists, deleting and recreating...[/yellow]")
        client.delete_collection(COLLECTION_NAME)
        
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=VECTOR_SIZE,
            distance=Distance.COSINE
        )
    )
    console.print(f"[green]Created collection '{COLLECTION_NAME}'[/green]")
    
def embed_and_store(chunks: list[dict], client: QdrantClient):
    """Embed each chunk and store in Qdrant."""
    points = []
    
    for chunk in track(chunks, description="Embedding chunks..."):
        vector = get_embedding(chunk["text"])
        
        point = PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload={
                "text": chunk["text"],
                **chunk["metadata"]
            }
        )
        points.append(point)
        
    client.upsert(
        collection_name=COLLECTION_NAME,
        points=points
    )

    console.print(f"[green]Stored {len(points)} points in Qdrant[/green]")
    
def run_ingestion():
    """Full ingestion pipeline — chunk, embed, store."""
    console.print("[bold cyan]Starting Korrupt ingestion pipeline[/bold cyan]")

    # Connect to Qdrant
    client = QdrantClient("localhost", port=6333)
    console.print("[green]Connected to Qdrant[/green]")

    # Setup collection
    setup_collection(client)

    # Load and chunk all collections
    chunks = chunk_all_collections(data_dir="../data")

    # Embed and store
    embed_and_store(chunks, client)

    # Verify
    count = client.count(collection_name=COLLECTION_NAME)
    console.print(f"\n[bold green]Ingestion complete — {count.count} vectors stored in Qdrant[/bold green]")
    
if __name__ == "__main__":
    run_ingestion()