from __future__ import annotations

import time
from typing import Any, Literal

from pydantic import BaseModel, Field


RiskLevel = Literal["none", "low", "medium", "high"]


def now_ms() -> int:
    """返回当前毫秒时间戳，模拟数据和日志统一使用这个时间基准。"""

    return int(time.time() * 1000)


class Quality(BaseModel):
    """
    传感器单条数据的质量说明。

    valid 表示这条数据是否可用，confidence 表示可信度。Agent 后续会根据这些字段
    决定是否可以给出强提醒，避免把低质量数据包装成确定结论。
    """

    valid: bool = True
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    error_code: str | None = None


class SensorHealth(BaseModel):
    """
    设备健康状态。

    这里不是读取真实硬件，而是用模拟字段表达“在线、延迟、置信度、错误码”等概念，
    方便后续替换为真实 OAK-D、雷达或 ESP32 网关。
    """

    device_id: str
    module: str
    online: bool = True
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    last_seen_seconds: int = Field(default=0, ge=0)
    error_codes: list[str] = Field(default_factory=list)


class UserProfile(BaseModel):
    """用户偏好画像，用于真实 Agent 的 memory/tool 上下文。"""

    user_id: str = "demo_user"
    preferred_tone: Literal["cute", "gentle", "professional"] = "gentle"
    reminder_cooldown_minutes: int = 30


class TodaySummary(BaseModel):
    """
    今日统计摘要。

    日报只能引用这里已有的数据和 event_log 中的事件，不允许凭空编造统计数字。
    """

    date: str
    sedentary_warning_count: int = 0
    hydration_warning_count: int = 0
    environment_warning_count: int = 0
    pet_action_count: int = 0
    drink_total_ml: int = 0
    longest_sedentary_minutes: int = 0


class KnowledgeChunk(BaseModel):
    """轻量 RAG 检索返回的知识片段。"""

    source: str
    chunk_text: str
    score: float


class JsonRecord(BaseModel):
    """SQLite 日志表中常用的 JSON 载荷包装。"""

    id: int | None = None
    created_at_ms: int = Field(default_factory=now_ms)
    payload: dict[str, Any]
