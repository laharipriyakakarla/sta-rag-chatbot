"""
rag_pipeline.py
Retrieves relevant timing paths from ChromaDB and answers questions using Claude.
"""

import os
import anthropic
import chromadb
from chromadb.utils import embedding_functions

CHROMA_DIR  = "./chroma_db"
COLLECTION  = "sta_timing_paths"
MODEL = "claude-sonnet-4-6"
MAX_RESULTS = 5  # number of paths to retrieve per query

SYSTEM_PROMPT = """You are an expert Static Timing Analysis (STA) engineer assistant.
You have access to real timing path data from an ibex RISC-V core implemented on ASAP7 7nm PDK using OpenROAD.

When answering questions:
- Be precise and technical — use proper STA terminology
- Reference specific path data (startpoint, endpoint, slack values) from the context
- Explain WHY a path is violated or what the slack margin means
- If asked about trends across stages (resizer → CTS → global route → finish), compare the data
- If the context doesn't contain enough info to answer, say so clearly

Design details:
- Design: ibex RISC-V core
- PDK: ASAP7 7nm
- Clock: core_clock, 1000ps period (1 GHz target)
- Tool: OpenROAD
- Stages in data: 3_resizer, 4_cts_final, 5_global_route, 6_finish
"""


def get_collection():
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    return client.get_collection(name=COLLECTION, embedding_function=ef)


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
            "similarity": 1 - distance  # cosine distance → similarity
        })
    return paths


def build_context(paths: list[dict]) -> str:
    """Format retrieved paths into a context block for Claude."""
    context_parts = []
    for i, p in enumerate(paths):
        meta = p["metadata"]
        context_parts.append(
            f"--- Path {i+1} (similarity: {p['similarity']:.2f}) ---\n"
            f"{p['document']}"
        )
    return "\n\n".join(context_parts)


def ask(question: str, verbose: bool = False) -> str:
    """Main RAG function: retrieve + generate."""
    # Step 1: Retrieve relevant paths
    paths = retrieve(question)

    if verbose:
        print(f"\nRetrieved {len(paths)} paths:")
        for p in paths:
            meta = p["metadata"]
            print(f"  slack={meta['slack']:.2f} ({meta['slack_status']}) "
                  f"| {meta['check_type']} | stage={meta['stage']} "
                  f"| sim={p['similarity']:.2f}")

    # Step 2: Build context
    context = build_context(paths)

    # Step 3: Query Claude
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    user_message = f"""Here is the relevant timing path data from the ibex RISC-V core STA reports:

{context}

Question: {question}

Please answer based on the timing data above."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}]
    )

    return response.content[0].text


if __name__ == "__main__":
    # Test with a few sample questions
    test_questions = [
        "Which path has the worst setup slack and why?",
        "Are there any hold violations in the design?",
        "How does the worst slack change from resizer to finish stage?",
    ]

    for q in test_questions:
        print(f"\n{'='*60}")
        print(f"Q: {q}")
        print(f"{'='*60}")
        answer = ask(q, verbose=True)
        print(f"\nA: {answer}")
        print()
