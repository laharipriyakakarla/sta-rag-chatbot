"""
rag_pipeline.py
Retrieves relevant timing paths from ChromaDB and answers questions using Claude.
All design details are read from config.json automatically.
"""

import os
import json
import anthropic
import chromadb
from chromadb.utils import embedding_functions

# ── Load config ─────────────────────────────────────────────────────────────────
with open("config.json") as f:
    CONFIG = json.load(f)

CHROMA_DIR  = CONFIG["chroma_dir"]
COLLECTION  = "sta_timing_paths"
MODEL       = "claude-sonnet-4-6"
MAX_RESULTS = 5


def build_system_prompt(stages: list[str]) -> str:
    """Build system prompt dynamically from config + actual stages in DB."""
    clock_ghz = 1000 / CONFIG["clock_period_ps"]
    stages_str = ", ".join(stages) if stages else "unknown"
    return f"""You are an expert Static Timing Analysis (STA) engineer assistant.
You have access to real timing path data from a {CONFIG['design']} implemented on {CONFIG['pdk']} PDK using {CONFIG['tool']}.

When answering questions:
- Be precise and technical — use proper STA terminology
- Reference specific path data (startpoint, endpoint, slack values) from the context
- Explain WHY a path is violated or what the slack margin means
- If asked about trends across stages, compare the data across stages
- If the context doesn't contain enough info to answer, say so clearly

Design details:
- Design: {CONFIG['design']}
- PDK: {CONFIG['pdk']}
- Tool: {CONFIG['tool']}
- Clock: {CONFIG['clock_name']}, {CONFIG['clock_period_ps']}ps period ({clock_ghz:.1f} GHz target)
- Stages in data: {stages_str}
"""


def get_collection():
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    return client.get_collection(name=COLLECTION, embedding_function=ef)


def get_stages() -> list[str]:
    """Get unique stage names from ChromaDB metadata."""
    try:
        collection = get_collection()
        results = collection.get(include=["metadatas"])
        stages = sorted(set(m["stage"] for m in results["metadatas"]))
        return stages
    except Exception:
        return []


def get_stats() -> dict:
    """Get summary stats from ChromaDB for sidebar display."""
    try:
        collection = get_collection()
        results = collection.get(include=["metadatas"])
        metadatas = results["metadatas"]
        total = len(metadatas)
        violated = sum(1 for m in metadatas if m["slack_status"] == "VIOLATED")
        met = total - violated
        stages = sorted(set(m["stage"] for m in metadatas))
        tools = sorted(set(m.get("tool", "unknown") for m in metadatas))
        worst_slack = min(m["slack"] for m in metadatas)
        return {
            "total": total,
            "met": met,
            "violated": violated,
            "stages": stages,
            "tools": tools,
            "worst_slack": worst_slack,
        }
    except Exception:
        return {}


def retrieve(query: str, n_results: int = MAX_RESULTS) -> list[dict]:
    """Retrieve top-n most relevant timing paths for the query."""
    collection = get_collection()
    results = collection.query(
        query_texts=[query],
        n_results=n_results
    )
    paths = []
    for doc, meta, distance in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0]
    ):
        paths.append({
            "document": doc,
            "metadata": meta,
            "similarity": 1 - distance
        })
    return paths


def build_context(paths: list[dict]) -> str:
    """Format retrieved paths into a context block for Claude."""
    context_parts = []
    for i, p in enumerate(paths):
        context_parts.append(
            f"--- Path {i+1} (similarity: {p['similarity']:.2f}) ---\n"
            f"{p['document']}"
        )
    return "\n\n".join(context_parts)


def ask(question: str, verbose: bool = False) -> str:
    """Main RAG function: retrieve + generate."""
    paths = retrieve(question)

    if verbose:
        print(f"\nRetrieved {len(paths)} paths:")
        for p in paths:
            meta = p["metadata"]
            print(f"  slack={meta['slack']:.2f} ({meta['slack_status']}) "
                  f"| {meta['check_type']} | stage={meta['stage']} "
                  f"| sim={p['similarity']:.2f}")

    context = build_context(paths)
    stages = get_stages()
    system_prompt = build_system_prompt(stages)

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    user_message = f"""Here is the relevant timing path data from the {CONFIG['design']} STA reports:

{context}

Question: {question}

Please answer based on the timing data above."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}]
    )

    return response.content[0].text


if __name__ == "__main__":
    test_questions = [
        "Which path has the worst setup slack and why?",
        "Are there any hold violations in the design?",
        "How does the worst slack change across stages?",
    ]
    for q in test_questions:
        print(f"\n{'='*60}")
        print(f"Q: {q}")
        print(f"{'='*60}")
        answer = ask(q, verbose=True)
        print(f"\nA: {answer}\n")
