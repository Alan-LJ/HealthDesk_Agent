from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import Quality, now_ms


class RawData(BaseModel):
    """
    Raw Data：模拟传感器原始数据。

    当前阶段不接真实硬件，所以 data 字段保持为字典，能够容纳压力、杯垫、温湿度、
    呼吸心率趋势等不同来源的原始值。
    """

    source: str
    device_id: str
    timestamp_ms: int = Field(default_factory=now_ms)
    seq: int = 0
    data: dict[str, Any]
    quality: Quality
