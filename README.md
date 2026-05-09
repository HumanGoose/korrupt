# Korrupt

Agentic Kubernetes incident analysis — RAG + LLMs

Korrupt connects directly to your Kubernetes cluster, autonomously runs diagnostic commands, retrieves relevant failure patterns from a vector knowledge base, and tells you exactly what is wrong and how to fix it. Every kubectl command it runs is visible in real time.

---

## Demo

Ask Korrupt a natural language question. It figures out what to investigate, runs the right kubectl commands, searches its knowledge base, and returns a structured diagnosis with remediation steps.

```
You:      "What is wrong with my cluster?"

Korrupt:  Runs kubectl get pods -A
          Runs kubectl describe pod memory-bomb-74b66d5c7c
          Runs kubectl logs memory-bomb-74b66d5c7c --previous
          Runs kubectl get events -n default
          Searches knowledge base for OOMKill patterns

          CLUSTER STATUS
          ✅ nginx-85fb7d6556       Running   healthy
          🔴 memory-bomb-74b66d5c7c OOMKilled exceeded 64Mi memory limit

          ROOT CAUSE
          Container attempted to allocate 200M but limit is 64Mi.
          Kernel OOMKiller terminated the process (exit code 137).

          REMEDIATION
          kubectl set resources deployment memory-bomb \
            --limits=memory=250Mi --requests=memory=200Mi
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Ingestion (one-time)                 │
│                                                             │
│   LitmusChaos → K8s cluster → Log collector → Chunker       │
│                                     ↓                       │
│                             Ollama embeddings               │
│                                     ↓                       │
│                            Qdrant vector DB                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                        Query (real-time)                    │
│                                                             │
│   User question → FastAPI agent → Claude (tool use)         │
│                                        ↓                    │
│                          ┌─────────────────────────┐        │
│                          │  kubectl commands (live) │       │
│                          │  Qdrant similarity search│       │
│                          └─────────────────────────┘        │
│                                        ↓                    │
│                         Root cause + remediation steps      │
│                                        ↓                    │
│                              Streamlit UI                   │
│                    (terminal left, chat right)              │
└─────────────────────────────────────────────────────────────┘
```

---

## How It Works

### Ingestion Pipeline (run once)

1. **Chaos injection** — LitmusChaos induces real failures on a local Kind cluster: pod deletion, OOMKill, container kill
2. **Log collection** — Python Kubernetes client collects pod logs, events, and pod details for each failure scenario
3. **Chunking** — logs are split into per-pod chunks with failure labels (`oomkill`, `pod_delete`, `container_kill`, `normal`)
4. **Embedding** — each chunk is embedded via Ollama (`nomic-embed-text`) and stored in Qdrant with metadata

### Query Pipeline (every request)

1. User asks a question in natural language
2. Claude receives the question + tool descriptions
3. Agent loop begins — Claude decides which tools to call:
   - `get_cluster_overview` — kubectl get pods -A
   - `describe_pod` — kubectl describe pod
   - `get_pod_logs` — kubectl logs (including previous container)
   - `get_events` — kubectl get events
   - `search_knowledge_base` — Qdrant similarity search against failure patterns
4. Each tool call executes real kubectl commands against the live cluster
5. Results are fed back to Claude iteratively until it has enough context
6. Claude returns a structured diagnosis: cluster status, root cause, remediation steps
7. All kubectl commands appear in the terminal in real time

---

## Tech Stack

| Layer | Technology |
|---|---|
| Kubernetes cluster | Kind (local) |
| Chaos engineering | LitmusChaos |
| Log collection | Python `kubernetes` client |
| Embeddings | Ollama + `nomic-embed-text` |
| Vector database | Qdrant |
| Agent / LLM | Claude Haiku (Anthropic API) |
| Backend | Python |
| UI | Streamlit |
| Deployment | Streamlit Cloud + Qdrant Cloud |

---

## Failure Scenarios in the Knowledge Base

| Scenario | Label | Key Signals |
|---|---|---|
| Healthy cluster | `normal` | All conditions True, restart_count: 0 |
| Pod deletion | `pod_delete` | New pod names each cycle, Killing events, regular interval |
| OOMKill | `oomkill` | Same pod, restart_count climbing, last_state reason: OOMKilled, exit_code: 137 |
| Container kill | `container_kill` | Same pod, Error status, exit_code: 137, BackOff events |

---

## Project Structure

```
korrupt/
├── collector/
│   ├── collector.py      # Collects logs, events, pod details from cluster
│   ├── chunker.py        # Splits JSON collections into per-pod chunks
│   ├── embedder.py       # Embeds chunks and stores in Qdrant
│   └── test_search.py    # Verifies retrieval is working
├── agent/
│   ├── tools.py          # kubectl tool implementations + Qdrant search
│   ├── prompts.py        # System prompt and tool descriptions for Claude
│   └── agent.py          # Agentic loop — tool use, response generation
├── ui/
│   └── app.py            # Streamlit UI — terminal + chat interface
├── data/                 # Collected failure datasets (gitignored)
├── chaos/                # LitmusChaos and deployment YAML files
└── requirements.txt
```

---

## Getting Started

### Prerequisites

- Docker
- Kind
- kubectl
- Python 3.12+
- Ollama
- Anthropic API key

### 1. Clone and install

```bash
git clone https://github.com/yourusername/korrupt.git
cd korrupt
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Start Ollama and pull models

```bash
ollama pull nomic-embed-text
ollama pull llama3
```

### 3. Set up environment

```bash
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env
```

### 4. Create a local cluster

```bash
sudo service docker start
kind create cluster --name k8s-ai-demo
kubectl get nodes
```

### 5. Run the ingestion pipeline

```bash
# Deploy a test app and inject failures
kubectl create deployment nginx --image=nginx
kubectl apply -f chaos/chaosengine.yaml

# Collect logs with labels
# Edit collector/collector.py to set label, then:
python collector/collector.py

# Start Qdrant
docker run -d --name qdrant -p 6333:6333 qdrant/qdrant

# Embed and store
cd collector && python embedder.py
```

### 6. Run Korrupt

```bash
streamlit run ui/app.py
```

Open `http://localhost:8501`

---

## Design Decisions

**Why RAG instead of fine-tuning?**
Fine-tuning requires GPU compute, days of training, and retraining whenever failure patterns change. RAG lets you update the knowledge base instantly by re-running the ingestion pipeline — no model changes required.

**Why labeled chaos data instead of real production logs?**
Generating failures with LitmusChaos gives us ground truth labels — we know exactly what failure was injected. This enables proper evaluation: given a query about OOMKill symptoms, does the system retrieve OOMKill chunks? Real logs rarely come with clean labels.

**Why chunk per pod instead of per event or per file?**
Each pod's logs, events, and health conditions together tell one coherent story. Chunking by pod preserves that context while keeping chunks small enough for precise retrieval. Chunking by event would lose context; chunking per file would blur multiple pods' stories together.

**Why a read-only tool boundary?**
Diagnostic commands (`get`, `describe`, `logs`, `events`) run automatically. Remediation commands that modify cluster state require explicit human confirmation. An AI should never make irreversible changes to production infrastructure without a human in the loop.

**Why Streamlit?**
Rapid prototyping. The UI was built in hours, not days. A production version would use FastAPI + WebSockets for real-time streaming without the page-reload flicker — Streamlit's known limitation for live-updating interfaces.

---

## Limitations

- Knowledge base covers 4 failure patterns — a production system would need significantly more scenarios
- Single-namespace monitoring by default — extend `collector.py` to collect across all namespaces
- Streamlit causes page flicker on each agent response — production UI would use WebSockets
- Ollama embeddings run locally — for deployed version, swap to a hosted embedding API

---

## What I Learned

- End-to-end RAG pipeline: chunking strategy, embedding tradeoffs, vector similarity search
- LLM tool use / function calling — the agent loop, stop conditions, multi-turn context management
- Kubernetes internals: pod lifecycle, event streams, container state, OOMKill signatures
- Chaos engineering: LitmusChaos, failure injection, labeled dataset generation
- Production ML system design: eval strategy, context window management, cost-per-query optimization
