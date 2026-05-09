SYSTEM_PROMPT = """You are Korrupt, an expert Kubernetes SRE assistant. 
You help engineers diagnose and fix cluster issues by analyzing logs, 
events, and pod states.

You have access to the following tools:
- get_cluster_overview: Get all pods and their current status
- describe_pod: Get detailed info about a specific pod
- get_pod_logs: Get logs from a pod (use previous=true for crashed pods)
- get_events: Get Kubernetes events
- search_knowledge_base: Search for similar failure patterns

RULES:
1. Always start by getting the cluster overview before diagnosing
2. For any unhealthy pod, always get its logs AND events
3. For crashed pods, always get previous logs (previous=true)
4. Search the knowledge base to find matching failure patterns
5. Never suggest destructive commands without explicitly warning the user
6. Always explain WHY something is failing, not just WHAT is failing
7. Structure your final response as:
   - CLUSTER STATUS (one line per pod with emoji)
   - ROOT CAUSE (what is actually wrong)
   - REMEDIATION (exact steps to fix it)

EMOJI GUIDE:
✅ Running and healthy
🔴 CrashLoopBackOff or OOMKilled  
⚠️  Pending or Unknown
🔄 Restarting frequently
"""

TOOL_DESCRIPTIONS = [
    {
        "name": "get_cluster_overview",
        "description": "Get status of all pods across all namespaces",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "describe_pod",
        "description": "Get detailed information about a specific pod including conditions, events, and resource usage",
        "input_schema": {
            "type": "object",
            "properties": {
                "pod_name": {
                    "type": "string",
                    "description": "Name of the pod"
                },
                "namespace": {
                    "type": "string",
                    "description": "Namespace of the pod, defaults to default"
                }
            },
            "required": ["pod_name"]
        }
    },
    {
        "name": "get_pod_logs",
        "description": "Get logs from a pod. Use previous=true for pods that have crashed to see what happened before the crash",
        "input_schema": {
            "type": "object",
            "properties": {
                "pod_name": {
                    "type": "string",
                    "description": "Name of the pod"
                },
                "namespace": {
                    "type": "string",
                    "description": "Namespace of the pod"
                },
                "previous": {
                    "type": "boolean",
                    "description": "Get logs from previous container run"
                }
            },
            "required": ["pod_name"]
        }
    },
    {
        "name": "get_events",
        "description": "Get Kubernetes events sorted by time, useful for seeing what happened recently in the cluster",
        "input_schema": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "Namespace to get events from"
                }
            },
            "required": []
        }
    },
    {
        "name": "search_knowledge_base",
        "description": "Search the Korrupt knowledge base for similar failure patterns and their solutions",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Description of the symptoms or failure to search for"
                }
            },
            "required": ["query"]
        }
    }
]