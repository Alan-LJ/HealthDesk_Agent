from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.rag.knowledge_base import KB_DIR, load_markdown_documents


DOMAIN_KEYWORDS = ["久坐", "饮水", "环境", "湿度", "温度", "桌宠", "设备", "降级", "心率", "呼吸"]


@dataclass(frozen=True)
class RagChunk:
    """RAG 知识片段，保留可用于向量库过滤的元数据。"""

    id: str
    source: str
    chunk_text: str
    chunk_index: int
    category: str
    metadata: dict[str, Any]


def tokenize_rag_text(text: str) -> list[str]:
    """轻量分词：覆盖英文、数字、中文连续词和健康领域关键词。"""

    words = re.findall(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]{2,}", text.lower())
    extra = [keyword for keyword in DOMAIN_KEYWORDS if keyword in text]
    if any(phrase in text for phrase in ["久坐", "坐太久", "坐了很久", "一直坐", "连续坐"]):
        extra.append("久坐")
    if any(phrase in text for phrase in ["饮水", "喝水", "补水", "口渴"]):
        extra.append("饮水")
    if any(phrase in text for phrase in ["空调", "太干", "干燥", "闷热"]):
        extra.append("环境")
    if any(phrase in text for phrase in ["低置信", "不可信", "离线", "传感器"]):
        extra.append("设备")
        extra.append("降级")
    return words + list(dict.fromkeys(extra))


def infer_category(source: str) -> str:
    """从知识库文件名推断 RAG category，用于 metadata filter。"""

    name = source.lower()
    if "sedentary" in name:
        return "sedentary"
    if "hydration" in name:
        return "hydration"
    if "environment" in name:
        return "environment"
    if "device" in name:
        return "device"
    if "pet_dialogue" in name or "template" in name:
        return "pet_dialogue"
    return "general"


def chunk_markdown_documents(kb_dir: Path = KB_DIR) -> list[RagChunk]:
    """读取本地 Markdown，并按标题/空行切成可检索片段。"""

    chunks: list[RagChunk] = []
    for source, text in load_markdown_documents(kb_dir):
        category = infer_category(source)
        parts = [part.strip() for part in re.split(r"\n(?=#)|\n\s*\n", text) if part.strip()]
        for index, part in enumerate(parts):
            chunk_id = _chunk_id(source, index, part)
            chunks.append(
                RagChunk(
                    id=chunk_id,
                    source=source,
                    chunk_text=part,
                    chunk_index=index,
                    category=category,
                    metadata={
                        "source": source,
                        "source_type": "local_markdown",
                        "chunk_index": index,
                        "category": category,
                        "content_hash": hashlib.sha1(part.encode("utf-8")).hexdigest(),
                    },
                )
            )
    return chunks


def _chunk_id(source: str, index: int, text: str) -> str:
    digest = hashlib.sha1(f"{source}:{index}:{text}".encode("utf-8")).hexdigest()[:16]
    return f"{Path(source).stem}-{index}-{digest}"
