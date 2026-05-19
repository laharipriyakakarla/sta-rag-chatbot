"""
embedder.py
Embeds parsed timing paths into a ChromaDB vector store.
Run this once to build the index; the RAG pipeline queries it at runtime.
"""

import os
import chromadb
from chromadb.utils import embedding_functions
from chunker import parse_all_reports, TimingPath


REPORTS_DIR = "./reports"
CHROMA_DIR  = "./chroma_db"
COLLECTION  = "sta_timing_paths"


def build_document(path: TimingPath) -> str:
    """
    Build a rich text document for embedding.
    Combines metadata + raw path text so semantic search works well.
    """
    doc = f"""
Stage: {path.stage}
Path Group: {path.path_group}
Path Type: {path.path_type} ({'setup' if path.path_type == 'max' else 'hold'})
Startpoint: {path.startpoint}
Endpoint: {path.endpoint}
Slack: {path.slack} ({path.slack_status})
Data Arrival Time: {path.data_arrival_time}
Data Required Time: {path.data_required_time}

Full Path:
{path.raw_text}
""".strip()
    return doc


def build_metadata(path: TimingPath) -> dict:
    """Metadata stored alongside each chunk — used for filtering."""
    return {
        "stage":            path.stage,
        "path_group":       path.path_group,
        "path_type":        path.path_type,
        "check_type":       "setup" if path.path_type == "max" else "hold",
        "slack":            path.slack,
        "slack_status":     path.slack_status,
        "startpoint":       path.startpoint[:200],
        "endpoint":         path.endpoint[:200],
        "data_arrival":     path.data_arrival_time or 0.0,
        "data_required":    path.data_required_time or 0.0,
    }


def embed_reports(reports_dir: str = REPORTS_DIR, chroma_dir: str = CHROMA_DIR):
    # Parse all reports
    print(f"Parsing reports from: {reports_dir}")
    paths = parse_all_reports(reports_dir)
    print(f"Total paths parsed: {len(paths)}")

    # Set up ChromaDB with local sentence-transformers embeddings (no API key needed)
    print("\nInitializing ChromaDB...")
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

    client = chromadb.PersistentClient(path=chroma_dir)

    # Drop and recreate collection for clean rebuild
    try:
        client.delete_collection(COLLECTION)
        print(f"Deleted existing collection: {COLLECTION}")
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"}
    )

    # Build documents, metadata, ids
    documents = []
    metadatas = []
    ids       = []

    for i, path in enumerate(paths):
        documents.append(build_document(path))
        metadatas.append(build_metadata(path))
        ids.append(f"path_{i:04d}")

    # Add to ChromaDB in one batch
    print(f"Embedding {len(documents)} paths into ChromaDB...")
    collection.add(
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )

    print(f"\nDone! Vector store saved to: {chroma_dir}")
    print(f"Collection '{COLLECTION}' has {collection.count()} entries")

    # Quick sanity check query
    print("\nSanity check — querying: 'worst violated setup path'")
    results = collection.query(
        query_texts=["worst violated setup path"],
        n_results=3
    )
    for i, (doc, meta) in enumerate(zip(results["documents"][0], results["metadatas"][0])):
        print(f"  [{i+1}] slack={meta['slack']:.2f} ({meta['slack_status']}) "
              f"| {meta['check_type']} | stage={meta['stage']}")
        print(f"       start: {meta['startpoint'][:60]}")


if __name__ == "__main__":
    embed_reports()
