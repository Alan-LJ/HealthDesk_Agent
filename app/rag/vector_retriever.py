from __future__ import annotations

import hashlib
import math
import shutil
from pathlib import Path
from typing import Any

from app.rag.bm25 import BM25Index
from app.rag.chunking import KB_DIR, RagChunk, chunk_markdown_documents, tokenize_rag_text
from app.schemas.common import KnowledgeChunk


class ChromaBackendError(RuntimeError):
    """Chroma 后端不可用时抛出的清晰运行时错误。"""


class HashingEmbeddingFunction:
    """无需下载模型的本地 embedding 函数。

    它用于让 Chroma 版本在开源项目中开箱可跑。后续如果接入 bge-m3、
    text-embedding 模型或本地 sentence-transformers，只需要替换这个类。
    """

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions

    @staticmethod
    def name() -> str:
        return "healthdesk_hashing_embedding"

    def get_config(self) -> dict[str, int]:
        return {"dimensions": self.dimensions}

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> "HashingEmbeddingFunction":
        return HashingEmbeddingFunction(dimensions=int(config.get("dimensions", 384)))

    @staticmethod
    def validate_config(config: dict[str, Any]) -> None:
        dimensions = int(config.get("dimensions", 384))
        if dimensions < 32:
            raise ValueError("HashingEmbeddingFunction dimensions must be >= 32")

    def default_space(self) -> str:
        return "cosine"

    def supported_spaces(self) -> list[str]:
        return ["cosine", "l2", "ip"]

    def is_legacy(self) -> bool:
        return False

    def __call__(self, input: list[str] | str) -> list[list[float]]:  # noqa: A002 - Chroma requires this argument name.
        return [self._embed(text) for text in _as_text_list(input)]

    def embed_query(self, input: list[str] | str) -> list[list[float]]:  # noqa: A002 - Chroma calls this keyword.
        """Chroma 1.x query path calls embed_query(input=...)."""

        return self(input)

    def embed_documents(self, input: list[str] | str) -> list[list[float]]:  # noqa: A002 - Chroma compatibility.
        """Compatibility with embedding-function interfaces that split query/docs."""

        return self(input)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in _embedding_tokens(text):
            digest = hashlib.sha1(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = -1.0 if digest[4] % 2 else 1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


class ChromaHybridRetriever:
    """Chroma 向量检索 + BM25 关键词检索的混合 RAG。"""

    backend_name = "chroma_hybrid"

    def __init__(
        self,
        *,
        persist_dir: str | Path = ".hdagent/chroma",
        collection_name: str = "healthdesk_rag",
        kb_dir: Path = KB_DIR,
        vector_weight: float = 0.65,
        bm25_weight: float = 0.35,
        embedding_dimensions: int = 384,
        rebuild_on_start: bool = True,
        reset_on_start: bool = False,
    ) -> None:
        self.persist_dir = Path(persist_dir)
        self.collection_name = collection_name
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight
        self.embedding_function = HashingEmbeddingFunction(embedding_dimensions)
        self.chunks = chunk_markdown_documents(kb_dir)
        self.chunk_by_id = {chunk.id: chunk for chunk in self.chunks}
        self.bm25 = BM25Index(self.chunks)
        if reset_on_start:
            self.reset_persist_dir()
        self._ensure_persist_dir_writable()
        self.client = self._build_client()
        self.collection = self._get_collection()
        if rebuild_on_start or self._collection_is_empty():
            self.rebuild()

    def reset_persist_dir(self) -> None:
        """删除并重建 Chroma 持久化目录。

        Chroma 索引是由本地 Markdown 知识库派生出的缓存；当旧索引损坏、
        SQLite 文件权限异常或版本升级后不兼容时，可以安全重建。
        """

        if self.persist_dir.exists():
            try:
                shutil.rmtree(self.persist_dir)
            except OSError as exc:
                raise ChromaBackendError(
                    f"无法重置 Chroma 持久化目录 {self.persist_dir}。"
                    "请确认没有其他 Python/uvicorn/桌宠进程正在占用该目录，"
                    "或手动删除该目录后重试。"
                ) from exc
        self.persist_dir.mkdir(parents=True, exist_ok=True)

    def rebuild(self) -> None:
        """重建 Chroma collection，确保 Markdown 与向量索引一致。"""

        self.persist_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass
        self.collection = self._get_collection()
        if not self.chunks:
            return
        try:
            self.collection.upsert(
                ids=[chunk.id for chunk in self.chunks],
                documents=[chunk.chunk_text for chunk in self.chunks],
                metadatas=[chunk.metadata for chunk in self.chunks],
            )
        except Exception as exc:
            raise ChromaBackendError(
                f"写入 Chroma collection 失败: {exc}。"
                "可尝试运行 `python scripts\\rebuild_rag_index.py --reset` 重建索引。"
            ) from exc

    def search(self, query: str, top_k: int = 3, filters: dict[str, Any] | None = None) -> list[KnowledgeChunk]:
        """执行向量相似度检索 + BM25 融合。"""

        filtered_chunks = self._filtered_chunks(filters)
        if not filtered_chunks:
            return []
        allowed_ids = {chunk.id for chunk in filtered_chunks}
        candidate_limit = min(len(filtered_chunks), max(top_k * 6, top_k, 10))
        vector_scores = self._vector_scores(query, candidate_limit, allowed_ids)
        bm25_scores = self.bm25.score(query, allowed_ids=allowed_ids)
        bm25_scores = _top_scores(bm25_scores, candidate_limit)
        vector_norm = _normalize_scores(vector_scores)
        bm25_norm = _normalize_scores(bm25_scores)
        candidate_ids = set(vector_norm) | set(bm25_norm)
        combined = {
            chunk_id: self.vector_weight * vector_norm.get(chunk_id, 0.0)
            + self.bm25_weight * bm25_norm.get(chunk_id, 0.0)
            for chunk_id in candidate_ids
        }
        ranked = sorted(combined.items(), key=lambda item: item[1], reverse=True)
        return [
            KnowledgeChunk(
                source=self.chunk_by_id[chunk_id].source,
                chunk_text=self.chunk_by_id[chunk_id].chunk_text,
                score=round(score, 4),
            )
            for chunk_id, score in ranked[:top_k]
            if chunk_id in self.chunk_by_id
        ]

    def _build_client(self) -> Any:
        try:
            import chromadb
        except ImportError as exc:
            raise ChromaBackendError("未安装 chromadb，无法启用 Chroma RAG。请运行: pip install chromadb") from exc
        try:
            return chromadb.PersistentClient(path=str(self.persist_dir))
        except Exception as exc:
            raise ChromaBackendError(
                f"启动 Chroma PersistentClient 失败: {exc}。"
                f"当前路径: {self.persist_dir}。"
                "请确认该目录可写、没有被其他进程占用；如旧索引损坏，"
                "运行 `python scripts\\rebuild_rag_index.py --reset` 后再启动服务。"
            ) from exc

    def _ensure_persist_dir_writable(self) -> None:
        try:
            self.persist_dir.mkdir(parents=True, exist_ok=True)
            probe = self.persist_dir / ".healthdesk_write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
        except OSError as exc:
            raise ChromaBackendError(
                f"Chroma 持久化目录不可写: {self.persist_dir}。"
                "请检查目录权限，关闭可能占用索引的 Python/uvicorn/桌宠进程，"
                "或设置 RAG_CHROMA_PATH 到当前用户可写目录。"
            ) from exc

    def _get_collection(self) -> Any:
        return self.client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self.embedding_function,
            metadata={"hnsw:space": "cosine"},
        )

    def _collection_is_empty(self) -> bool:
        try:
            return int(self.collection.count()) == 0
        except Exception:
            return True

    def _vector_scores(self, query: str, candidate_limit: int, allowed_ids: set[str]) -> dict[str, float]:
        try:
            result = self.collection.query(
                query_texts=[query],
                n_results=min(len(self.chunks), max(candidate_limit, 1)),
                include=["distances"],
            )
        except Exception as exc:
            raise ChromaBackendError(
                f"Chroma 向量查询失败: {exc}。"
                "当前强制向量库模式不会静默退回关键词检索，请先修复 Chroma 索引。"
            ) from exc
        ids = (result.get("ids") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        scores: dict[str, float] = {}
        for chunk_id, distance in zip(ids, distances):
            if chunk_id not in allowed_ids:
                continue
            scores[chunk_id] = 1.0 / (1.0 + max(float(distance), 0.0))
            if len(scores) >= candidate_limit:
                break
        return scores

    def _filtered_chunks(self, filters: dict[str, Any] | None) -> list[RagChunk]:
        if not filters:
            return self.chunks
        categories = _as_set(filters.get("category"))
        sources = _as_set(filters.get("source"))
        selected: list[RagChunk] = []
        for chunk in self.chunks:
            if categories and chunk.category not in categories:
                continue
            if sources and chunk.source not in sources:
                continue
            selected.append(chunk)
        return selected

    def close(self) -> None:
        """释放 Chroma 客户端资源，避免测试或短命令进程悬挂。"""

        client = getattr(self, "client", None)
        if client is None:
            return
        close = getattr(client, "close", None)
        if callable(close):
            close()
            return
        system = getattr(client, "_system", None)
        stop = getattr(system, "stop", None)
        if callable(stop):
            stop()


def _embedding_tokens(text: str) -> list[str]:
    tokens = tokenize_rag_text(text)
    compact = re_space(text)
    tokens.extend(compact[index : index + 2] for index in range(max(len(compact) - 1, 0)))
    tokens.extend(compact[index : index + 3] for index in range(max(len(compact) - 2, 0)))
    return [token for token in tokens if token.strip()]


def _as_text_list(value: list[str] | str) -> list[str]:
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def re_space(text: str) -> str:
    return "".join(text.lower().split())


def _as_set(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {value}
    if isinstance(value, (list, tuple, set)):
        return {str(item) for item in value}
    return {str(value)}


def _normalize_scores(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    max_score = max(scores.values())
    if max_score <= 0:
        return {key: 0.0 for key in scores}
    return {key: value / max_score for key, value in scores.items()}


def _top_scores(scores: dict[str, float], limit: int) -> dict[str, float]:
    return dict(sorted(scores.items(), key=lambda item: item[1], reverse=True)[:limit])
