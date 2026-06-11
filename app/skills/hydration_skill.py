from __future__ import annotations

from pydantic import BaseModel

from app.schemas.common import RiskLevel


class HydrationInput(BaseModel):
    drink_today_ml: int
    last_drink_minutes_ago: int
    humidity_percent: float
    temperature_c: float


class HydrationOutput(BaseModel):
    risk_level: RiskLevel
    should_remind: bool
    reason: str
    suggested_action: str


class HydrationAnalysisSkill:
    """饮水分析 Skill，用今日饮水量、间隔时间和环境干燥程度做温和提醒。"""

    def run(self, data: HydrationInput) -> HydrationOutput:
        risk: RiskLevel = "none"
        if data.drink_today_ml < 600 and data.last_drink_minutes_ago >= 90:
            risk = "medium"
        elif data.drink_today_ml < 900 and data.last_drink_minutes_ago >= 120:
            risk = "low"
        if risk in {"low", "medium"} and (data.humidity_percent < 35 or data.temperature_c > 28):
            risk = "high" if risk == "medium" else "medium"
        should = risk != "none"
        reason = f"今日饮水 {data.drink_today_ml} ml，距离上次饮水 {data.last_drink_minutes_ago} 分钟"
        return HydrationOutput(risk_level=risk, should_remind=should, reason=reason, suggested_action="喝几口水，并观察办公环境是否偏干" if should else "饮水节奏正常，继续保持")
