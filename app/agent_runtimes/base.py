from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentRunRequest(BaseModel):
    """一次真实 Agent runtime 运行请求。

    task 是用户或系统事件提出的目标；user_id 预留给多用户扩展。
    当前项目只保留 LangGraph + DeepSeek 真实 Agent pipeline。
    """

    task: str
    user_id: str = "default"


class AgentRunResult(BaseModel):
    """真实 runtime 返回给 API 的结构。"""

    runtime: Literal["langgraph_deepseek"]
    trace_id: str
    status: str = "ok"
    message: str
    stop_reason: str | None = None
    final_output: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BaseAgentRuntime(ABC):
    """真实 Agent runtime 抽象基类。"""

    runtime_name: Literal["langgraph_deepseek"]

    @abstractmethod
    def run(self, request: AgentRunRequest) -> AgentRunResult:
        """运行一次 Agent 任务并返回结构化结果。"""
