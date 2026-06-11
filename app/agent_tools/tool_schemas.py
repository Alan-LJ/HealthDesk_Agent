from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.event import PetAction


class ToolObservation(BaseModel):
    """工具返回给 Agent 的统一 observation。

    LangGraph 的下一轮 reason node 会读取 observation 再决定下一步 action。
    这里保留 raw_data，方便后续节点按工具类型更新 risk_tags、retrieved_chunks 等状态。
    """

    tool_name: str
    success: bool = True
    summary: str
    raw_data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GetCurrentStateInput(BaseModel):
    user_id: str = "default"


class GetRecentEventsInput(BaseModel):
    user_id: str = "default"
    limit: int = Field(default=10, ge=1, le=100)


class GetTodaySummaryInput(BaseModel):
    user_id: str = "default"


class GetSensorHealthInput(BaseModel):
    user_id: str = "default"


class GetMemorySummaryInput(BaseModel):
    user_id: str = "default"


class AnalyzeOfficeHealthSnapshotInput(BaseModel):
    user_id: str = "default"
    include_pet_action: bool = True


class SearchKnowledgeInput(BaseModel):
    query: str
    top_k: int = Field(default=3, ge=1, le=10)


class SavePetActionInput(BaseModel):
    action: PetAction


class SaveDailyReportInput(BaseModel):
    report: dict[str, Any]


class UpdateUserMemoryInput(BaseModel):
    user_id: str = "default"
    summary: str


class DeviceGuardianHandoffInput(BaseModel):
    user_id: str = "default"
    reason: str = Field(default="模型判断需要设备守护专家确认数据可信度")
