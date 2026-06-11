from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import RiskLevel


Priority = Literal["low", "medium", "high"]


class PetActionOutput(BaseModel):
    """新 Agent 输出给桌宠的动作结构。

    这个模型比旧 `PetAction` 更偏向 Agent final output：它说明桌宠要怎么表现，
    也说明为什么触发该动作。真正写入前端/数据库时，后续可以再转换成旧的
    `app.schemas.event.PetAction`。
    """

    emotion: str
    animation: str
    message: str
    priority: Priority = "low"
    interruptible: bool = True
    reason: str


class RecommendationOutput(BaseModel):
    """单条办公健康建议。

    建议必须带 category、risk_level 和 reason，避免 Agent 只给一句无法追溯的建议。
    """

    category: str
    risk_level: RiskLevel = "none"
    reason: str
    suggested_action: str
    data_sources: list[str] = Field(default_factory=list)


class HealthAgentFinalOutput(BaseModel):
    """LangGraph + DeepSeek Health Agent 的最终结构化输出。

    API 和桌宠只能消费通过该模型校验后的结果。DeepSeek 如果输出非法 JSON，
    后续 finalize_node 会 repair 或 fallback，而不是直接返回未校验内容。
    """

    task_type: str
    risk_tags: list[str] = Field(default_factory=list)
    health_summary: str
    recommendations: list[RecommendationOutput] = Field(default_factory=list)
    pet_action: PetActionOutput | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    data_sources_used: list[str] = Field(default_factory=list)
    tools_called: list[str] = Field(default_factory=list)
    guardrail_status: dict[str, bool | str | list[str]] = Field(default_factory=dict)
    runtime: Literal["langgraph_deepseek"]
    trace_id: str
    stop_reason: str

    @field_validator("health_summary")
    @classmethod
    def summary_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("health_summary 不能为空")
        return value


class DeviceGuardianOutput(BaseModel):
    """设备守护专家输出。

    它用于告诉主 Agent 哪些数据可信、哪些建议必须降级，避免低置信度数据被包装成强结论。
    """

    system_status: Literal["healthy", "degraded", "unknown"]
    degraded_modules: list[str] = Field(default_factory=list)
    impact: str
    advice_constraints: list[str] = Field(default_factory=list)
    user_message: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class DailyReportOutput(BaseModel):
    """日报 Agent 的结构化输出。

    日报必须引用已有统计、事件或 memory，不允许编造未记录的数据。
    """

    report_title: str
    summary: str
    key_findings: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    tomorrow_focus: list[str] = Field(default_factory=list)
    data_sources_used: list[str] = Field(default_factory=list)
