import pytest

from app.agent_tools.rag_tools import build_rag_tools
from app.rag.bm25 import BM25Index
from app.rag.chunking import chunk_markdown_documents
from app.rag.simple_retriever import SimpleRetriever
from app.rag.vector_retriever import ChromaHybridRetriever


def test_retriever_finds_health_chunks():
    hits = SimpleRetriever().search("久坐 饮水 环境", top_k=3)
    assert len(hits) == 3
    assert any("久坐" in hit.chunk_text for hit in hits)


def test_bm25_scores_domain_keywords():
    chunks = chunk_markdown_documents()
    scores = BM25Index(chunks).score("连续坐太久 应该活动")

    assert scores
    best_id = max(scores, key=scores.get)
    best = next(chunk for chunk in chunks if chunk.id == best_id)
    assert best.category == "sedentary"


def test_rag_tools_apply_category_filters():
    tools = {tool.name: tool for tool in build_rag_tools(SimpleRetriever())}

    pet_obs = tools["search_pet_templates"].invoke({"query": "久坐提醒", "top_k": 2})
    device_obs = tools["search_device_docs"].invoke({"query": "低置信度", "top_k": 2})

    assert pet_obs.raw_data["chunks"]
    assert all(chunk["source"] == "pet_dialogue_templates.md" for chunk in pet_obs.raw_data["chunks"])
    assert device_obs.raw_data["chunks"]
    assert all(chunk["source"] == "device_diagnosis.md" for chunk in device_obs.raw_data["chunks"])


def test_chroma_hybrid_retriever_searches_with_bm25_fusion(tmp_path):
    pytest.importorskip("chromadb")

    try:
        retriever = ChromaHybridRetriever(persist_dir=tmp_path / "chroma", rebuild_on_start=True)
    except Exception as exc:
        pytest.skip(f"Chroma is installed but not available in this environment: {exc}")
    hits = retriever.search("我坐了很久 肩膀僵硬 需要活动", top_k=3, filters={"category": "sedentary"})

    assert hits
    assert all(hit.source == "sedentary_guidelines.md" for hit in hits)
    assert all(hit.score >= 0 for hit in hits)
