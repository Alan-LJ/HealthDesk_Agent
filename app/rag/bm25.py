from __future__ import annotations

import math
from collections import Counter

from app.rag.chunking import RagChunk, tokenize_rag_text


class BM25Index:
    """小规模 Markdown 知识库使用的 BM25 检索器。

    这里不引入额外依赖，避免为了几十个知识片段增加新的运行成本。
    """

    def __init__(self, chunks: list[RagChunk], *, k1: float = 1.5, b: float = 0.75) -> None:
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self.doc_tokens = [tokenize_rag_text(chunk.chunk_text) for chunk in chunks]
        self.doc_lengths = [len(tokens) for tokens in self.doc_tokens]
        self.avg_doc_length = sum(self.doc_lengths) / len(self.doc_lengths) if self.doc_lengths else 0.0
        self.term_freqs = [Counter(tokens) for tokens in self.doc_tokens]
        self.doc_freqs = self._build_doc_freqs()
        self.idf = self._build_idf()

    def score(self, query: str, *, allowed_ids: set[str] | None = None) -> dict[str, float]:
        """返回 chunk_id -> BM25 分数。"""

        query_terms = tokenize_rag_text(query)
        if not query_terms or not self.chunks:
            return {}
        allowed_ids = allowed_ids or {chunk.id for chunk in self.chunks}
        scores: dict[str, float] = {}
        for index, chunk in enumerate(self.chunks):
            if chunk.id not in allowed_ids:
                continue
            score = 0.0
            doc_length = self.doc_lengths[index] or 1
            term_freq = self.term_freqs[index]
            for term in query_terms:
                freq = term_freq.get(term, 0)
                if freq <= 0:
                    continue
                numerator = freq * (self.k1 + 1)
                denominator = freq + self.k1 * (1 - self.b + self.b * doc_length / (self.avg_doc_length or 1))
                score += self.idf.get(term, 0.0) * numerator / denominator
            if score > 0:
                scores[chunk.id] = score
        return scores

    def _build_doc_freqs(self) -> Counter[str]:
        doc_freqs: Counter[str] = Counter()
        for tokens in self.doc_tokens:
            doc_freqs.update(set(tokens))
        return doc_freqs

    def _build_idf(self) -> dict[str, float]:
        total = len(self.doc_tokens)
        return {
            term: math.log(1 + (total - freq + 0.5) / (freq + 0.5))
            for term, freq in self.doc_freqs.items()
        }
