from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class FeatureData(BaseModel):
    """
    Feature Data：从 Raw Data 抽取后的办公健康特征。

    真实项目中这里会由视觉、压力、杯垫、环境传感器算法生成；当前原型由模拟器直接产出。
    """

    sitting: bool = True
    sedentary_minutes: int = Field(default=0, ge=0)
    posture_change_level: Literal["low", "medium", "high"] = "medium"
    drink_today_ml: int = Field(default=0, ge=0)
    last_drink_minutes_ago: int = Field(default=0, ge=0)
    temperature_c: float = 24.0
    humidity_percent: float = Field(default=50.0, ge=0.0, le=100.0)
    breath_rate_bpm: int | None = None
    heart_rate_bpm: int | None = None
    vital_quality: Literal["low", "medium", "high"] = "high"
