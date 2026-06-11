from __future__ import annotations

import math
import re
from collections import Counter

from app.rag.knowledge_base import load_markdown_documents
from app.schemas.common import KnowledgeChunk


def _tokens(text: str) -> list[str]:
    """非常轻量的分词：支持英文单词、数字和常见中文关键词匹配。"""

    words = re.findall(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]{2,}", text.lower())
    extra = [kw for kw in ["久坐", "饮水", "环境", "湿度", "温度", "桌宠", "设备", "降级", "心率", "呼吸"] if kw in text]
    return words + extra


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
        self.chunks = self._load_chunks()

    def _load_chunks(self) -> list[KnowledgeChunk]:
        chunks: list[KnowledgeChunk] = []
        for source, text in load_markdown_documents():
            parts = [part.strip() for part in re.split(r"\n(?=#)|\n\s*\n", text) if part.strip()]
            for part in parts:
                chunks.append(KnowledgeChunk(source=source, chunk_text=part, score=0.0))
        return chunks

    def search(self, query: str, top_k: int = 3) -> list[KnowledgeChunk]:
        """检索与 query 最相关的 top_k 个知识片段。"""

        q = Counter(_tokens(query))
        scored: list[KnowledgeChunk] = []
        for chunk in self.chunks:
            score = _cosine(q, Counter(_tokens(chunk.chunk_text)))
            if any(token in chunk.chunk_text for token in q):
                score += 0.1
            if score > 0:
                scored.append(KnowledgeChunk(source=chunk.source, chunk_text=chunk.chunk_text, score=round(score, 4)))
        ranked = sorted(scored, key=lambda item: item.score, reverse=True)

        # 先保证不同知识源都有机会进入结果，避免 top_k 被同一份文档的多个 chunk 挤占。
        selected: list[KnowledgeChunk] = []
        seen_sources: set[str] = set()
        for item in ranked:
            if item.source not in seen_sources:
                selected.append(item)
                seen_sources.add(item.source)
            if len(selected) >= top_k:
                return selected
        for item in ranked:
            if item not in selected:
                selected.append(item)
            if len(selected) >= top_k:
                break
        return selected
