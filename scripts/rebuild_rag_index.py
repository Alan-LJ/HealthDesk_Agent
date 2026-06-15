from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent_runtimes.settings import load_runtime_settings
from app.rag.vector_retriever import ChromaHybridRetriever


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild HealthDesk Chroma RAG index.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete the existing Chroma persist directory before rebuilding the index.",
    )
    args = parser.parse_args()

    settings = load_runtime_settings()
    retriever = ChromaHybridRetriever(
        persist_dir=settings.rag_chroma_path,
        collection_name=settings.rag_collection_name,
        vector_weight=settings.rag_hybrid_vector_weight,
        bm25_weight=settings.rag_hybrid_bm25_weight,
        embedding_dimensions=settings.rag_embedding_dimensions,
        rebuild_on_start=False,
        reset_on_start=args.reset or settings.rag_chroma_reset_on_start,
    )
    try:
        retriever.rebuild()
        print(
            f"Rebuilt Chroma RAG index: collection={settings.rag_collection_name}, "
            f"chunks={len(retriever.chunks)}, path={settings.rag_chroma_path}"
        )
    finally:
        retriever.close()


if __name__ == "__main__":
    main()
