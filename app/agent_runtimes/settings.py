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

    candidates = [Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env"]
    for path in candidates:
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


class AgentRuntimeSettings(BaseModel):
    """LangGraph + DeepSeek 真实 Agent runtime 的集中配置。"""

    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_thinking: DeepSeekThinkingMode = "disabled"
    deepseek_reasoning_effort: str = "high"
    database_path: str = "healthdesk.db"
    max_agent_steps: int = Field(default=6, ge=1)
    max_same_tool_calls: int = Field(default=2, ge=1)
    rag_top_k: int = Field(default=3, ge=1)
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
        database_path=os.getenv("DATABASE_PATH", os.getenv("HEALTHDESK_DB_PATH", "healthdesk.db")),
        max_agent_steps=_env_int("MAX_AGENT_STEPS", 6),
        max_same_tool_calls=_env_int("MAX_SAME_TOOL_CALLS", 2),
        rag_top_k=_env_int("RAG_TOP_K", 3),
        trace_to_sqlite=_env_bool("TRACE_TO_SQLITE", True),
    )
