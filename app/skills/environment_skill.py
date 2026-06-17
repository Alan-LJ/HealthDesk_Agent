from __future__ import annotations

from pydantic import BaseModel

from app.schemas.environment import ComfortStatus, EnvironmentAlertLevel, EnvironmentThresholdSettings, assess_environment_comfort


class EnvironmentInput(BaseModel):
    temperature_c: float
    humidity_percent: float


class EnvironmentOutput(BaseModel):
    comfort_status: ComfortStatus
    alert_level: EnvironmentAlertLevel = "none"
    reason: str
    suggested_action: str


class EnvironmentComfortSkill:
    """环境舒适度 Skill，用温湿度规则生成非医疗化办公建议。"""

    def __init__(self, settings: EnvironmentThresholdSettings | None = None) -> None:
        self.settings = settings

    def run(self, data: EnvironmentInput) -> EnvironmentOutput:
        assessment = assess_environment_comfort(data.temperature_c, data.humidity_percent, self.settings)
        return EnvironmentOutput(
            comfort_status=assessment.comfort_status,
            alert_level=assessment.alert_level,
            reason=assessment.reason,
            suggested_action=assessment.suggested_action,
        )
