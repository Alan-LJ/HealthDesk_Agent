from __future__ import annotations

from pydantic import BaseModel


class VitalTrendInput(BaseModel):
    breath_rate_bpm: int | None = None
    heart_rate_bpm: int | None = None
    vital_quality: str = "high"


class VitalTrendOutput(BaseModel):
    trend_summary: str
    can_use_for_advice: bool
    reason: str


class VitalTrendSkill:
    """生命体征趋势 Skill，只做办公趋势参考，绝不输出医疗诊断。"""

    def run(self, data: VitalTrendInput) -> VitalTrendOutput:
        if data.vital_quality == "low":
            return VitalTrendOutput(trend_summary="数据质量不足，暂不分析趋势", can_use_for_advice=False, reason="vital_quality 为 low")
        if data.breath_rate_bpm is None and data.heart_rate_bpm is None:
            return VitalTrendOutput(trend_summary="暂无趋势数据", can_use_for_advice=False, reason="未提供呼吸或心率趋势值")
        return VitalTrendOutput(trend_summary="呼吸和心率数据仅作为办公状态趋势参考", can_use_for_advice=True, reason="数据质量可用于非医疗级趋势提示")
