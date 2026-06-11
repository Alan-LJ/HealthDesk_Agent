from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from app.schemas.common import now_ms


EventType = Literal[
    "sedentary_warning",
    "hydration_warning",
    "environment_warning",
    "vital_trend_update",
    "device_degraded",
    "pet_action_triggered",
    "daily_report_generated",
]


class EventData(BaseModel):
    """
    Event Data：离散事件。

    事件是 Agent 和日报最重要的事实来源之一，例如一次久坐提醒、一次设备降级、
    一次桌宠动作都会写入 event_log。
    """

    event_type: EventType
    timestamp_ms: int = Field(default_factory=now_ms)
    severity: Literal["info", "low", "medium", "high"] = "info"
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)


class PetAction(BaseModel):
    """桌宠可执行动作，前端或桌宠进程可以直接消费这个 JSON。"""

    action_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp_ms: int = Field(default_factory=now_ms)
    emotion: str
    animation: str
    message: str
    priority: Literal["low", "medium", "high"] = "low"
    bubble_type: Literal["hint", "success", "question", "system"] = "hint"
    display_seconds: int = Field(default=6, ge=1, le=60)
    metadata: dict[str, Any] = Field(default_factory=dict)
