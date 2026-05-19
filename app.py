"""
app.py
Streamlit chat interface for the STA timing analysis chatbot.
All design info is read dynamically from config.json and ChromaDB.
Run with: python3 -m streamlit run app.py
"""

import json
import streamlit as st
from rag_pipeline import ask, retrieve, get_stats, CONFIG

# ── Load stats from ChromaDB ────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_stats():
    return get_stats()

stats = load_stats()
stages = stats.get("stages", [])
tools  = stats.get("tools", [])

# ── Page config ─────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=f"STA Chatbot — {CONFIG['design']}",
    page_icon="⏱️",
    layout="wide"
)

# ── Sidebar ──────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⏱️ STA Chatbot")

    # Design info — from config.json
    clock_ghz = 1000 / CONFIG["clock_period_ps"]
    st.markdown(f"""
    **Design:** {CONFIG['design']}  
    **PDK:** {CONFIG['pdk']}  
    **Tool:** {CONFIG['tool']}  
    **Clock:** {CONFIG['clock_name']} @ {clock_ghz:.1f} GHz  
    """)

    st.divider()

    # DB stats — from ChromaDB
    if stats:
        st.markdown("**Database stats:**")
        col1, col2, col3 = st.columns(3)
        col1.metric("Total", stats.get("total", 0))
        col2.metric("🟢 MET", stats.get("met", 0))
        col3.metric("🔴 Fail", stats.get("violated", 0))
        if stats.get("worst_slack") is not None:
            st.caption(f"Worst slack: `{stats['worst_slack']:.2f} ps`")

    st.divider()

    # Stages — read dynamically from ChromaDB
    if stages:
        st.markdown("**Stages in database:**")
        for s in stages:
            st.markdown(f"- `{s}`")
    
    # Tools detected
    if tools and tools != ["unknown"]:
        st.markdown("**Tools detected:**")
        for t in tools:
            st.markdown(f"- `{t}`")

    st.divider()

    # Example questions
    st.markdown("**Try asking:**")
    example_questions = [
        "Which path has the worst setup slack?",
        "Are there any hold violations?",
        "How does slack change across stages?",
        f"What is the worst path in the {CONFIG['clock_name']} group?",
        "Show me violated paths and explain why they fail",
        "Which stage has the most violations?",
        "Compare setup vs hold margins",
    ]
    for q in example_questions:
        if st.button(q, use_container_width=True):
            st.session_state.pending_question = q

    st.divider()
    n_results = st.slider("Paths retrieved per query", 3, 10, 5)
    show_retrieved = st.checkbox("Show retrieved paths", value=False)

    if st.button("🗑️ Clear chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ── Session state ────────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

# ── Main area ────────────────────────────────────────────────────────────────────
st.title("STA Timing Analysis Chatbot")
st.caption(f"Ask questions about your {CONFIG['design']} {CONFIG['pdk']} timing reports — powered by RAG + Claude")


def show_retrieved_paths(paths):
    with st.expander("📂 Retrieved timing paths"):
        for i, p in enumerate(paths):
            meta = p["metadata"]
            slack_color = "🔴" if meta["slack_status"] == "VIOLATED" else "🟢"
            st.markdown(
                f"**Path {i+1}** {slack_color} "
                f"slack=`{meta['slack']:.2f}ps` | "
                f"`{meta['check_type']}` | "
                f"stage=`{meta['stage']}` | "
                f"sim=`{p['similarity']:.2f}`"
            )
            st.caption(f"Start: {meta['startpoint'][:80]}")
            st.caption(f"End:   {meta['endpoint'][:80]}")


# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("retrieved_paths"):
            show_retrieved_paths(msg["retrieved_paths"])


def handle_question(question):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Retrieving paths and analyzing..."):
            paths = retrieve(question, n_results=n_results)
            answer = ask(question)
        st.markdown(answer)
        if show_retrieved:
            show_retrieved_paths(paths)

    retrieved = paths if show_retrieved else []
    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "retrieved_paths": retrieved
    })
    st.rerun()


# Handle sidebar button click
if st.session_state.pending_question:
    question = st.session_state.pending_question
    st.session_state.pending_question = None
    handle_question(question)

# Handle text input
if question := st.chat_input("Ask about your timing data..."):
    handle_question(question)
