import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import anthropic
import streamlit as st
from dotenv import load_dotenv
from agent.agent import run_agent
from agent.tools import run_kubectl

load_dotenv()

st.set_page_config(
    page_title="Korrupt",
    page_icon="💀",
    layout="wide"
)

st.markdown("""
<style>
.terminal-chrome {
    background: #1e1e1e;
    border-radius: 10px 10px 0 0;
    padding: 10px 16px;
    display: flex;
    align-items: center;
    gap: 8px;
    border: 1px solid #333;
    border-bottom: none;
}
.dot { width:12px; height:12px; border-radius:50%; display:inline-block; }
.dot-r { background:#ff5f57; }
.dot-y { background:#febc2e; }
.dot-g { background:#28c840; }
.terminal-title {
    color: #999;
    font-family: monospace;
    font-size: 13px;
    margin-left: 8px;
}
.terminal-body {
    background: #0d1117;
    color: #00ff00;
    font-family: 'Courier New', monospace;
    font-size: 12px;
    padding: 16px;
    height: 420px;
    overflow-y: auto;
    overflow-x: auto;
    border: 1px solid #333;
    border-top: none;
    border-radius: 0 0 10px 10px;
    white-space: pre;
    word-break: normal;
    line-height: 1.4;
}
</style>
""", unsafe_allow_html=True)

# ── Session state ────────────────────────────────────
if "console_lines" not in st.session_state:
    st.session_state.console_lines = [
        ("info", "Korrupt v1.0 — Kubernetes Incident Analysis"),
        ("out",  "─" * 48),
        ("out",  ""),
    ]
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "pending_response" not in st.session_state:
    st.session_state.pending_response = False
if "pending_message" not in st.session_state:
    st.session_state.pending_message = ""
if "suggestions" not in st.session_state:
    st.session_state.suggestions = [
        "What is the health of my cluster?",
        "Show me all running pods",
        "Are there any issues I should know about?"
    ]


# ── Console helpers ──────────────────────────────────
def add_cmd(text):
    st.session_state.console_lines.append(("cmd", f"$ {text}"))

def add_out(text):
    for line in str(text).strip().split("\n"):
        st.session_state.console_lines.append(("out", f"  {line}"))

def add_info(text):
    st.session_state.console_lines.append(("info", text))

def build_console_html():
    lines = []
    for kind, text in st.session_state.console_lines:
        escaped = (text
                   .replace("&", "&amp;")
                   .replace("<", "&lt;")
                   .replace(">", "&gt;"))
        if kind == "cmd":
            lines.append(f'<span style="color:#00ff00">{escaped}</span>')
        elif kind == "info":
            lines.append(f'<span style="color:#58a6ff">{escaped}</span>')
        else:
            lines.append(f'<span style="color:#aaaaaa">{escaped}</span>')
    return "\n".join(lines)


# ── Suggestion generator ─────────────────────────────
def generate_suggestions(chat_history: list) -> list[str]:
    if not chat_history:
        return [
            "What is the health of my cluster?",
            "Show me all running pods",
            "Are there any issues I should know about?"
        ]

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    last_messages = chat_history[-4:]
    context = "\n".join([
        f"{m['role'].upper()}: {m['content'][:300]}"
        for m in last_messages
    ])

    try:
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": f"""Given this Kubernetes support conversation, suggest 3 short follow-up questions the user might want to ask next. Return ONLY a JSON array of 3 strings, nothing else.

Conversation:
{context}

Rules:
- Each suggestion under 8 words
- Must be relevant to what was just discussed
- Action-oriented (how to fix, show me, explain why)"""
            }]
        )
        text = response.content[0].text.strip()
        return json.loads(text)[:3]
    except Exception:
        return ["How do I fix this?", "Show me the logs", "What caused this?"]


# ── Agent runner ─────────────────────────────────────
def run_agent_with_updates(user_message: str) -> str:
    def on_tool_call(tool_name, tool_input):
        if tool_name == "get_cluster_overview":
            add_cmd("kubectl get pods -A -o wide")
        elif tool_name == "describe_pod":
            pod = tool_input.get("pod_name", "")
            ns = tool_input.get("namespace", "default")
            add_cmd(f"kubectl describe pod {pod} -n {ns}")
        elif tool_name == "get_pod_logs":
            pod = tool_input.get("pod_name", "")
            ns = tool_input.get("namespace", "default")
            prev = "--previous" if tool_input.get("previous") else ""
            add_cmd(f"kubectl logs {pod} -n {ns} {prev}".strip())
        elif tool_name == "get_events":
            ns = tool_input.get("namespace", "default")
            add_cmd(f"kubectl get events -n {ns} --sort-by='.lastTimestamp'")

    def on_tool_result(tool_name, result):
        if tool_name != "search_knowledge_base":
            lines = str(result).strip().split("\n")
            for line in lines:
                add_out(line)
            st.session_state.console_lines.append(("out", ""))

    return run_agent(
        user_message,
        on_tool_call=on_tool_call,
        on_tool_result=on_tool_result
    )


# ── Header ───────────────────────────────────────────
st.markdown("# Korrupt")
st.caption("Kubernetes incident analysis — agentic RAG + LLMs")

with st.expander("What is Korrupt?"):
    st.markdown("""
Korrupt is an AI-powered Kubernetes incident analysis tool. It connects directly to your cluster, runs diagnostic commands autonomously, and tells you exactly what is wrong and how to fix it.

**What it can do:**
- Diagnose failing pods — OOMKill, CrashLoopBackOff, pending, evicted
- Read logs and events to find root causes
- Search a knowledge base of known failure patterns
- Suggest exact remediation commands

**How it works:**
When you ask a question, Korrupt runs a sequence of kubectl commands against your cluster, retrieves relevant failure patterns from a vector database, and uses an LLM to synthesize a diagnosis. Every command it runs appears in the terminal on the left.

**Example questions to try:**
- *"What is wrong with my cluster?"*
- *"Why is my pod in CrashLoopBackOff?"*
- *"How do I fix the OOMKill issue?"*
- *"Show me everything that is unhealthy"*
""")

st.divider()

left_col, right_col = st.columns([1, 1], gap="large")

# ── LEFT — Terminal ──────────────────────────────────
with left_col:
    st.markdown("""
    <div class="terminal-chrome">
        <span class="dot dot-r"></span>
        <span class="dot dot-y"></span>
        <span class="dot dot-g"></span>
        <span class="terminal-title">korrupt — zsh</span>
    </div>""", unsafe_allow_html=True)

    console_html = build_console_html()
    st.markdown(
        f'<div class="terminal-body">{console_html}</div>',
        unsafe_allow_html=True
    )

    cmd_col, btn_col = st.columns([5, 1])
    with cmd_col:
        kubectl_cmd = st.text_input(
            "cmd",
            placeholder="get pods -A",
            label_visibility="collapsed",
            key="kubectl_cmd"
        )
    with btn_col:
        run_btn = st.button("▶ Run", use_container_width=True)

    if run_btn and kubectl_cmd:
        add_cmd(f"kubectl {kubectl_cmd}")
        result = run_kubectl(kubectl_cmd)
        add_out(result.get("output", "No output"))
        st.rerun()

# ── RIGHT — Chat ─────────────────────────────────────
with right_col:
    # Chat messages
    chat_box = st.container(height=400)
    with chat_box:
        if not st.session_state.chat_history and not st.session_state.pending_response:
            st.markdown("*Ask me anything about your cluster.*")

        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if st.session_state.pending_response:
            with st.chat_message("assistant"):
                with st.spinner("Investigating your cluster..."):
                    response = run_agent_with_updates(
                        st.session_state.pending_message
                    )
                st.markdown(response)

            st.session_state.chat_history.append({
                "role": "assistant",
                "content": response
            })
            st.session_state.pending_response = False
            st.session_state.pending_message = ""
            st.session_state.suggestions = generate_suggestions(
                st.session_state.chat_history
            )
            st.rerun()

    # Suggestions just above the input
    sug_cols = st.columns(3)
    quick_action = None
    for i, (col, suggestion) in enumerate(
        zip(sug_cols, st.session_state.suggestions)
    ):
        with col:
            if st.button(
                suggestion,
                use_container_width=True,
                key=f"sug_{i}"
            ):
                quick_action = suggestion

    # Chat input — Enter submits natively
    user_input = st.chat_input("Ask Korrupt anything...")

    message_to_send = quick_action or user_input or None

    if message_to_send:
        st.session_state.chat_history.append({
            "role": "user",
            "content": message_to_send
        })
        st.session_state.pending_response = True
        st.session_state.pending_message = message_to_send
        # Console only gets kubectl commands — no user messages
        st.rerun()