from __future__ import annotations

import math
from collections import Counter
from typing import Any

from app.rag.chunking import RagChunk, chunk_markdown_documents, tokenize_rag_text
from app.schemas.common import KnowledgeChunk


def _cosine(a: Counter[str], b: Counter[str]) -> float:
    """用词频余弦相似度给 chunk 排序，后续可以替换成 FAISS/Milvus 向量检索。"""

    keys = set(a) | set(b)
    dot = sum(a[k] * b[k] for k in keys)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class SimpleRetriever:
    """
    轻量 RAG 原型。

    它读取本地 Markdown，按标题/空行切 chunk，再用关键词与词频相似度检索。
    生产环境可以把这个类替换成 FAISS、Milvus 或云向量数据库，Agent 层无需大改。
    """

    def __init__(self) -> None:
        self.chunk_records = chunk_markdown_documents()
        self.chunks = [
            KnowledgeChunk(source=chunk.source, chunk_text=chunk.chunk_text, score=0.0)
            for chunk in self.chunk_records
        ]
        self.backend_name = "simple_keyword"

    def search(self, query: str, top_k: int = 3, filters: dict[str, Any] | None = None) -> list[KnowledgeChunk]:
        """检索与 query 最相关的 top_k 个知识片段。"""

        q = Counter(tokenize_rag_text(query))
        scored: list[tuple[RagChunk, float]] = []
        for chunk in self._filtered_chunks(filters):
            score = _cosine(q, Counter(tokenize_rag_text(chunk.chunk_text)))
            if any(token in chunk.chunk_text for token in q):
                score += 0.1
            if score > 0:
                scored.append((chunk, score))
        ranked = sorted(scored, key=lambda item: item[1], reverse=True)

        # 先保证不同知识源都有机会进入结果，避免 top_k 被同一份文档的多个 chunk 挤占。
        selected: list[KnowledgeChunk] = []
        seen_sources: set[str] = set()
        for chunk, score in ranked:
            if chunk.source not in seen_sources:
                selected.append(KnowledgeChunk(source=chunk.source, chunk_text=chunk.chunk_text, score=round(score, 4)))
                seen_sources.add(chunk.source)
            if len(selected) >= top_k:
                return selected
        selected_ids = {(item.source, item.chunk_text) for item in selected}
        for chunk, score in ranked:
            key = (chunk.source, chunk.chunk_text)
            if key not in selected_ids:
                selected.append(KnowledgeChunk(source=chunk.source, chunk_text=chunk.chunk_text, score=round(score, 4)))
            if len(selected) >= top_k:
                break
        return selected

    def _filtered_chunks(self, filters: dict[str, Any] | None) -> list[RagChunk]:
        if not filters:
            return self.chunk_records
        categories = _as_set(filters.get("category"))
        sources = _as_set(filters.get("source"))
        return [
            chunk
            for chunk in self.chunk_records
            if (not categories or chunk.category in categories) and (not sources or chunk.source in sources)
        ]


def _as_set(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {value}
    if isinstance(value, (list, tuple, set)):
        return {str(item) for item in value}
    return {str(value)}
