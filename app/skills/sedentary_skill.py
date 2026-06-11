from __future__ import annotations

from pydantic import BaseModel

from app.schemas.common import RiskLevel


class SedentaryInput(BaseModel):
    sedentary_minutes: int
    posture_change_level: str
    last_reminder_minutes_ago: int = 999
    device_confidence: float = 1.0


class SedentaryOutput(BaseModel):
    risk_level: RiskLevel
    should_remind: bool
    reason: str
    suggested_action: str


class SedentaryAnalysisSkill:
    """
    久坐分析 Skill。

    Skill 可以理解为 Agent 可调用的“专业能力”。这里用可解释规则计算久坐风险，
    再把结果交给 Agent 组织成结构化建议和桌宠动作。
    """

    def run(self, data: SedentaryInput) -> SedentaryOutput:
        """输入久坐分钟数、坐姿变化和设备置信度，输出风险等级与建议。"""

        if data.device_confidence < 0.6:
            return SedentaryOutput(risk_level="low", should_remind=False, reason="座椅相关数据可信度较低，久坐判断降级为参考", suggested_action="可以稍后确认坐姿数据恢复后再提醒")
        if data.sedentary_minutes < 45:
            level: RiskLevel = "none"
        elif data.sedentary_minutes < 60:
            level = "low"
        elif data.sedentary_minutes <= 90:
            level = "medium"
        else:
            level = "high"
        if data.posture_change_level == "low" and level == "low":
            level = "medium"
        elif data.posture_change_level == "low" and level == "medium":
            level = "high"
        should = level != "none" and data.last_reminder_minutes_ago >= 30
        action = "站起活动 2 到 3 分钟，顺便放松肩颈" if should else "保持当前节奏，注意定时改变坐姿"
        return SedentaryOutput(risk_level=level, should_remind=should, reason=f"连续坐姿 {data.sedentary_minutes} 分钟，坐姿变化为 {data.posture_change_level}", suggested_action=action)
