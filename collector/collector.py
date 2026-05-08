import json
import os
from datetime import datetime, UTC
from pathlib import Path

from kubernetes import client, config
from rich.console import Console
from rich.panel import Panel

console = Console()

def connect_to_cluster():
    config.load_kube_config()
    return client.CoreV1Api()

def collect_pod_logs(v1, namespace="default"):
    console.print("[bold cyan]Collecting pod logs...[/bold cyan]")
    
    pods = v1.list_namespaced_pod(namespace=namespace)
    collected = []
    
    for pod in pods.items:
        pod_name = pod.metadata.name
        try:
            logs = v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                tail_lines=200
            )
            collected.append({
                "source": "pod_log",
                "pod": pod_name,
                "namespace": namespace,
                "timestamp": datetime.now(UTC).isoformat(),
                "content": logs
            })
            console.print(f"  ✓ Collected logs from [green]{pod_name}[/green]")
        except Exception as e:
            console.print(f"  ✗ Failed to get logs from [red]{pod_name}[/red]: {e}")

    return collected

def collect_events(v1, namespace='default'):
    console.print("[bold cyan]Collecting events...[/bold cyan]")

    events = v1.list_namespaced_event(namespace=namespace)
    collected = []

    for event in events.items:
        collected.append({
            "source": "k8s_event",
            "reason": event.reason,
            "message": event.message,
            "type": event.type,
            "object": event.involved_object.name,
            "timestamp": str(event.last_timestamp),
        })

    console.print(f"  ✓ Collected [green]{len(collected)}[/green] events")
    return collected

def collect_pod_details(v1, namespace="default"):
    console.print("[bold cyan]Collecting pod details...[/bold cyan]")

    pods = v1.list_namespaced_pod(namespace=namespace)
    collected = []

    for pod in pods.items:
        pod_name = pod.metadata.name
        status = pod.status

        collected.append({
            "source": "pod_detail",
            "pod": pod_name,
            "namespace": namespace,
            "phase": status.phase,
            "conditions": [
                {
                    "type": c.type,
                    "status": c.status
                }
                for c in (status.conditions or [])
            ],
            "restart_count": sum(
                cs.restart_count
                for cs in (status.container_statuses or [])
            ),
            "timestamp": datetime.now(UTC).isoformat()
        })
        console.print(f"  ✓ Collected details for [green]{pod_name}[/green]")

    return collected

def save_collection(data: dict, label: str):
    output_dir = Path("data")
    output_dir.mkdir(exist_ok=True)

    filename = f"{label}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    filepath = output_dir / filename

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, default=str)

    console.print(Panel(
        f"Saved to [bold]{filepath}[/bold]",
        title="Collection Complete",
        style="green"
    ))
    return filepath

def run_collection(label: str = "normal", namespace: str = "default"):
    console.print(Panel(
        f"Starting collection | label=[bold]{label}[/bold] | namespace=[bold]{namespace}[/bold]",
        title="K8s Log Collector",
        style="cyan"
    ))
    
    v1 = connect_to_cluster()
    
    data = {
        "label": label,
        "collected_at": datetime.now(UTC).isoformat(),
        "namespace": namespace,
        "pod_logs": collect_pod_logs(v1, namespace),
        "events": collect_events(v1, namespace),
        "pod_details": collect_pod_details(v1, namespace)
    }
    
    return save_collection(data, label)

if __name__ == "__main__":
    run_collection(label="normal")
