import json
from pathlib import Path
from datetime import datetime, UTC


def load_collection(filepath: str) -> dict:
    with open(filepath, "r") as f:
        return json.load(f)
    

def chunk_collection(collection: dict) -> list[dict]:
    """
    Splits collection into meaningful chunks
    One chunk per pod
    """
    chunks = []
    label = collection["label"]
    collected_at = collection["collected_at"]
    namespace = collection["namespace"]
    
    pod_names = set()
    
    for log in collection["pod_logs"]:
        pod_names.add(log["pod"])
        
    for detail in collection["pod_details"]:
        pod_names.add(detail["pod"])

    for event in collection["events"]:
        if "object" in event:
            pod_names.add(event["object"])
    
    for pod_name in pod_names:
        pod_logs = [
            log["content"]
            for log in collection["pod_logs"]
            if log["pod"] == pod_name
        ]
        pod_events = [
            {
                "reason": e["reason"],
                "message": e["message"],
                "type": e["type"],
                "timestamp": e["timestamp"]
            }
            for e in collection["events"]
            if e.get("object") == pod_name
        ]
        pod_details = [
            {
                "phase": d["phase"],
                "restart_count": d["restart_count"],
                "conditions": d["conditions"],
                "last_state": d.get("last_state", [])
            }
            for d in collection["pod_details"]
            if d["pod"] == pod_name
        ]
        
        chunk_text = f"""
            failure_label: {label}
            pod: {pod_name}
            namespace: {namespace}
            collected_at: {collected_at}

            --- POD DETAILS ---
            {json.dumps(pod_details, indent=2, default=str)}

            --- EVENTS ---
            {json.dumps(pod_events, indent=2, default=str)}

            --- LOGS ---
            {' '.join(pod_logs)[:2000]}
            """.strip()
            
        chunks.append({
            "text": chunk_text,
            "metadata": {
                "label": label,
                "pod": pod_name,
                "namespace": namespace,
                "collected_at": collected_at,
                "source_file": str(filepath) if 'filepath' in dir() else ""
            }
        })
        
    return chunks

def chunk_all_collections(data_dir: str="data") -> list[dict]:
    """Chunk all JSON files in the data directory"""
    data_path = Path(data_dir)
    all_chunks = []
    
    json_files = list(data_path.glob("*.json"))
    print(f"Found {len(json_files)} collection files")
    
    for filepath in json_files:
        print(f"Chunking {filepath.name}...")
        collection = load_collection(str(filepath))
        chunks = chunk_collection(collection)
        
        for chunk in chunks:
            chunk["metadata"]["source_file"] = filepath.name
        
        all_chunks.extend(chunks)
        print(f"  → {len(chunks)} chunks")
    
    print(f"\nTotal chunks: {len(all_chunks)}")
    return all_chunks


if __name__ == "__main__":
    chunks = chunk_all_collections()

    # Print first chunk so we can see what it looks like
    if chunks:
        print("\n--- SAMPLE CHUNK ---")
        print(chunks[0]["text"])
        print("\n--- METADATA ---")
        print(json.dumps(chunks[0]["metadata"], indent=2))