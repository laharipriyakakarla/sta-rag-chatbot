"""
app.py
Streamlit chat interface for the STA timing analysis chatbot.
Run with: streamlit run app.py
"""

import streamlit as st
from rag_pipeline import ask, retrieve

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="STA Chatbot — ibex RISC-V / ASAP7",
    page_icon="⏱️",
    layout="wide"
)

# ── Sidebar ─────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⏱️ STA Chatbot")
    st.markdown("""
    **Design:** ibex RISC-V Core  
    **PDK:** ASAP7 7nm  
    **Tool:** OpenROAD  
    **Clock:** core_clock @ 1 GHz  
    """)

    st.divider()
    st.markdown("**Stages in database:**")
    st.markdown("""
    - `3_resizer` — Post-resizer
    - `4_cts_final` — Post-CTS
    - `5_global_route` — Post-global route
    - `6_finish` — Final signoff
    """)

    st.divider()
    st.markdown("**Try asking:**")
    example_questions = [
        "Which path has the worst setup slack?",
        "Are there any hold violations?",
        "How does slack change across stages?",
        "What is the worst path in the core_clock group?",
        "Show me violated paths and explain why they fail",
        "What is the clock skew in the final stage?",
        "Which stage has the most violations?",
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

# ── Session state ───────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

# ── Main area ───────────────────────────────────────────────────────────────────
st.title("STA Timing Analysis Chatbot")
st.caption("Ask questions about your ibex RISC-V ASAP7 timing reports — powered by RAG + Claude")

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("retrieved_paths"):
            with st.expander("📂 Retrieved timing paths"):
                for i, p in enumerate(msg["retrieved_paths"]):
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

# Handle sidebar button click
if st.session_state.pending_question:
    question = st.session_state.pending_question
    st.session_state.pending_question = None
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Retrieving paths and analyzing..."):
            paths = retrieve(question, n_results=n_results)
            answer = ask(question)
        st.markdown(answer)
        if show_retrieved:
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

    retrieved = paths if show_retrieved else []
    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "retrieved_paths": retrieved
    })
    st.rerun()

# Handle text input
if question := st.chat_input("Ask about your timing data..."):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Retrieving paths and analyzing..."):
            paths = retrieve(question, n_results=n_results)
            answer = ask(question)
        st.markdown(answer)
        if show_retrieved:
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

    retrieved = paths if show_retrieved else []
    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "retrieved_paths": retrieved
    })
