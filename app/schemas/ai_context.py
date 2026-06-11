from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import KnowledgeChunk, SensorHealth, TodaySummary, UserProfile
from app.schemas.event import EventData
from app.schemas.state import StateData


class AIContext(BaseModel):
    """
    AI Context：Agent 可以使用的上下文。

    这个结构把“当前状态、近期事件、今日统计、用户画像、设备状态、记忆、RAG 知识”
    放在同一个可信边界内。Agent 只能基于这些输入和工具返回生成建议。
    """

    current_state: StateData
    recent_events: list[EventData] = Field(default_factory=list)
    today_summary: TodaySummary
    user_profile: UserProfile = Field(default_factory=UserProfile)
    sensor_health: list[SensorHealth] = Field(default_factory=list)
    memory_summary: str = ""
    retrieved_knowledge: list[KnowledgeChunk] = Field(default_factory=list)
