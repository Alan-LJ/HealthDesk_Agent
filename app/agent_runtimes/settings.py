from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


DeepSeekThinkingMode = Literal["enabled", "disabled"]


def _configured_secret(value: str | None) -> bool:
    """判断 API Key 是否真的配置。

    旧工程常用 XXX 作为占位符。这里把空字符串和 XXX 都视为未配置，
    这样 auto runtime 不会误判为可以访问 DeepSeek。
    """

    return bool(value and value.strip() and value.strip().upper() != "XXX")


def _load_env_file() -> None:
    """轻量读取项目根目录 .env。

    项目当前没有强依赖 python-dotenv。为了让 settings 在第二步就能工作，
    这里先复用一个极简读取器：只处理 KEY=VALUE，且不覆盖已存在的系统环境变量。
    """

    project_root = Path(__file__).resolve().parents[2]
    candidates = [
        project_root / ".hdagent" / ".env",
        Path.cwd() / ".hdagent" / ".env",
        Path.cwd() / ".env",
        project_root / ".env",
    ]
    seen: set[Path] = set()
    for path in candidates:
        path = path.resolve()
        if path in seen:
            continue
        seen.add(path)
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text or text.startswith("#") or "=" not in text:
                continue
            key, value = text.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


class AgentRuntimeSettings(BaseModel):
    """LangGraph + DeepSeek 真实 Agent runtime 的集中配置。"""

    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_thinking: DeepSeekThinkingMode = "disabled"
    deepseek_reasoning_effort: str = "high"
    database_path: str = ".hdagent/healthdesk.db"
    max_agent_steps: int = Field(default=6, ge=1)
    max_same_tool_calls: int = Field(default=2, ge=1)
    rag_top_k: int = Field(default=3, ge=1)
    rag_backend: str = "auto"
    rag_chroma_path: str = ".hdagent/chroma"
    rag_collection_name: str = "healthdesk_rag"
    rag_hybrid_vector_weight: float = Field(default=0.65, ge=0.0, le=1.0)
    rag_hybrid_bm25_weight: float = Field(default=0.35, ge=0.0, le=1.0)
    rag_embedding_dimensions: int = Field(default=384, ge=32)
    rag_rebuild_on_start: bool = True
    rag_chroma_reset_on_start: bool = False
    trace_to_sqlite: bool = True

    @property
    def has_deepseek_key(self) -> bool:
        """DeepSeek Key 是否可用于真实 runtime。"""

        return _configured_secret(self.deepseek_api_key)


def load_runtime_settings() -> AgentRuntimeSettings:
    """从环境变量加载 runtime settings。"""

    _load_env_file()
    return AgentRuntimeSettings(
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/"),
        deepseek_thinking=os.getenv("DEEPSEEK_THINKING", "disabled").strip().lower(),  # type: ignore[arg-type]
        deepseek_reasoning_effort=os.getenv("DEEPSEEK_REASONING_EFFORT", "high").strip().lower(),
        database_path=os.getenv("DATABASE_PATH", os.getenv("HEALTHDESK_DB_PATH", ".hdagent/healthdesk.db")),
        max_agent_steps=_env_int("MAX_AGENT_STEPS", 6),
        max_same_tool_calls=_env_int("MAX_SAME_TOOL_CALLS", 2),
        rag_top_k=_env_int("RAG_TOP_K", 3),
        rag_backend=os.getenv("RAG_BACKEND", "auto").strip().lower(),
        rag_chroma_path=os.getenv("RAG_CHROMA_PATH", ".hdagent/chroma"),
        rag_collection_name=os.getenv("RAG_CHROMA_COLLECTION", "healthdesk_rag"),
        rag_hybrid_vector_weight=_env_float("RAG_HYBRID_VECTOR_WEIGHT", 0.65),
        rag_hybrid_bm25_weight=_env_float("RAG_HYBRID_BM25_WEIGHT", 0.35),
        rag_embedding_dimensions=_env_int("RAG_EMBEDDING_DIMENSIONS", 384),
        rag_rebuild_on_start=_env_bool("RAG_REBUILD_ON_START", True),
        rag_chroma_reset_on_start=_env_bool("RAG_CHROMA_RESET_ON_START", False),
        trace_to_sqlite=_env_bool("TRACE_TO_SQLITE", True),
    )
