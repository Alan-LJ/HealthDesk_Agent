from __future__ import annotations

from typing import Any, Protocol

from app.agent_tools.local_tool import LocalToolBinding, make_tool
from app.agent_tools.tool_schemas import SearchKnowledgeInput, ToolObservation
from app.rag.simple_retriever import SimpleRetriever
from app.rag.vector_retriever import ChromaHybridRetriever


class RagRetriever(Protocol):
    backend_name: str

    def search(self, query: str, top_k: int = 3, filters: dict[str, Any] | None = None) -> list:
        ...


def _chunks_to_payload(chunks: list) -> list[dict]:
    return [
        {
            "source": chunk.source,
            "chunk_text": chunk.chunk_text,
            "score": chunk.score,
            "metadata": {"source_type": "local_markdown"},
        }
        for chunk in chunks
    ]


def search_health_knowledge_handler(retriever: RagRetriever, data: SearchKnowledgeInput) -> ToolObservation:
    chunks = retriever.search(data.query, top_k=data.top_k, filters={"category": ["sedentary", "hydration", "environment"]})
    return ToolObservation(
        tool_name="search_health_knowledge",
        summary=f"检索到 {len(chunks)} 条健康知识片段。RAG 只提供外部知识，不代表用户当前状态。",
        raw_data={"chunks": _chunks_to_payload(chunks)},
        metadata={
            "query": data.query,
            "top_k": data.top_k,
            "rag_boundary": "knowledge_only",
            "retriever_backend": getattr(retriever, "backend_name", "unknown"),
        },
    )


def search_pet_templates_handler(retriever: RagRetriever, data: SearchKnowledgeInput) -> ToolObservation:
    query = f"桌宠 话术 模板 {data.query}"
    chunks = retriever.search(query, top_k=data.top_k, filters={"category": "pet_dialogue"})
    return ToolObservation(
        tool_name="search_pet_templates",
        summary=f"检索到 {len(chunks)} 条桌宠话术片段。",
        raw_data={"chunks": _chunks_to_payload(chunks)},
        metadata={
            "query": query,
            "top_k": data.top_k,
            "rag_boundary": "templates_only",
            "retriever_backend": getattr(retriever, "backend_name", "unknown"),
        },
    )


def search_device_docs_handler(retriever: RagRetriever, data: SearchKnowledgeInput) -> ToolObservation:
    query = f"设备 降级 置信度 {data.query}"
    chunks = retriever.search(query, top_k=data.top_k, filters={"category": "device"})
    return ToolObservation(
        tool_name="search_device_docs",
        summary=f"检索到 {len(chunks)} 条设备说明片段。",
        raw_data={"chunks": _chunks_to_payload(chunks)},
        metadata={
            "query": query,
            "top_k": data.top_k,
            "rag_boundary": "device_docs_only",
            "retriever_backend": getattr(retriever, "backend_name", "unknown"),
        },
    )


def build_rag_tools(retriever: RagRetriever | None = None) -> list[LocalToolBinding[Any]]:
    """创建 RAG 工具绑定。"""

    retriever = retriever or build_default_rag_retriever()
    return [
        make_tool(
            name="search_health_knowledge",
            description="检索久坐、饮水、环境舒适度等健康建议知识。注意：RAG 不能替代当前状态工具。",
            args_schema=SearchKnowledgeInput,
            func=lambda data: search_health_knowledge_handler(retriever, data),
        ),
        make_tool(
            name="search_pet_templates",
            description="检索桌宠话术模板，用于生成温和、非医疗化的桌宠提示。",
            args_schema=SearchKnowledgeInput,
            func=lambda data: search_pet_templates_handler(retriever, data),
        ),
        make_tool(
            name="search_device_docs",
            description="检索设备降级和数据可信度说明。只能提供解释依据，不能替代 sensor_health。",
            args_schema=SearchKnowledgeInput,
            func=lambda data: search_device_docs_handler(retriever, data),
        ),
    ]


def build_default_rag_retriever(settings: Any | None = None) -> RagRetriever:
    """根据配置选择 RAG backend。

    `auto` 会优先启用 Chroma hybrid；如果 chromadb 尚未安装，则降级到 SimpleRetriever。
    显式配置为 `chroma` 或 `hybrid` 时，如果 Chroma 不可用会抛出清晰错误。
    """

    if settings is None:
        from app.agent_runtimes.settings import load_runtime_settings

        settings = load_runtime_settings()
    backend = settings.rag_backend
    if backend in {"auto", "chroma", "hybrid", "chroma_hybrid"}:
        try:
            return ChromaHybridRetriever(
                persist_dir=settings.rag_chroma_path,
                collection_name=settings.rag_collection_name,
                vector_weight=settings.rag_hybrid_vector_weight,
                bm25_weight=settings.rag_hybrid_bm25_weight,
                embedding_dimensions=settings.rag_embedding_dimensions,
                rebuild_on_start=settings.rag_rebuild_on_start,
            )
        except Exception:
            if backend != "auto":
                raise
    return SimpleRetriever()
