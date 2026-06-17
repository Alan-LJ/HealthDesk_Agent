from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import now_ms
from app.schemas.environment import ComfortStatus


class StateData(BaseModel):
    """
    State Data：当前用户办公健康状态。

    它是 Feature Data 的“当前快照”，也是 Agent 每次分析时最核心的输入。
    """

    timestamp_ms: int = Field(default_factory=now_ms)
    at_desk: bool = True
    sitting: bool = True
    sedentary_minutes: int = Field(default=0, ge=0)
    posture_change_level: Literal["low", "medium", "high"] = "medium"
    drink_today_ml: int = Field(default=0, ge=0)
    last_drink_minutes_ago: int = Field(default=0, ge=0)
    temperature_c: float = 24.0
    humidity_percent: float = Field(default=50.0, ge=0.0, le=100.0)
    comfort_status: ComfortStatus = "comfortable"
    breath_rate_bpm: int | None = None
    heart_rate_bpm: int | None = None
    vital_quality: Literal["low", "medium", "high"] = "high"
    device_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
