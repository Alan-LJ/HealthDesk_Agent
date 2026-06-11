from app.rag.simple_retriever import SimpleRetriever


def test_retriever_finds_health_chunks():
    hits = SimpleRetriever().search("久坐 饮水 环境", top_k=3)
    assert len(hits) == 3
    assert any("久坐" in hit.chunk_text for hit in hits)
