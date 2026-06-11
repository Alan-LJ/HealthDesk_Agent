from __future__ import annotations

from typing import Any

from app.agent_tools.local_tool import LocalToolBinding, make_tool
from app.agent_tools.tool_schemas import SearchKnowledgeInput, ToolObservation
from app.rag.simple_retriever import SimpleRetriever


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


def search_health_knowledge_handler(retriever: SimpleRetriever, data: SearchKnowledgeInput) -> ToolObservation:
    chunks = retriever.search(data.query, top_k=data.top_k)
    return ToolObservation(
        tool_name="search_health_knowledge",
        summary=f"检索到 {len(chunks)} 条健康知识片段。RAG 只提供外部知识，不代表用户当前状态。",
        raw_data={"chunks": _chunks_to_payload(chunks)},
        metadata={"query": data.query, "top_k": data.top_k, "rag_boundary": "knowledge_only"},
    )


def search_pet_templates_handler(retriever: SimpleRetriever, data: SearchKnowledgeInput) -> ToolObservation:
    query = f"桌宠 话术 模板 {data.query}"
    chunks = retriever.search(query, top_k=data.top_k)
    return ToolObservation(
        tool_name="search_pet_templates",
        summary=f"检索到 {len(chunks)} 条桌宠话术片段。",
        raw_data={"chunks": _chunks_to_payload(chunks)},
        metadata={"query": query, "top_k": data.top_k, "rag_boundary": "templates_only"},
    )


def search_device_docs_handler(retriever: SimpleRetriever, data: SearchKnowledgeInput) -> ToolObservation:
    query = f"设备 降级 置信度 {data.query}"
    chunks = retriever.search(query, top_k=data.top_k)
    return ToolObservation(
        tool_name="search_device_docs",
        summary=f"检索到 {len(chunks)} 条设备说明片段。",
        raw_data={"chunks": _chunks_to_payload(chunks)},
        metadata={"query": query, "top_k": data.top_k, "rag_boundary": "device_docs_only"},
    )


def build_rag_tools(retriever: SimpleRetriever | None = None) -> list[LocalToolBinding[Any]]:
    """创建 RAG 工具绑定。"""

    retriever = retriever or SimpleRetriever()
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
