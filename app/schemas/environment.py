from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import now_ms


ComfortStatus = Literal["comfortable", "dry", "hot", "cold", "humid", "mixed"]
EnvironmentAlertLevel = Literal["none", "watch", "warning"]


class EnvironmentThresholdSettings(BaseModel):
    """用户可配置的温湿度适宜区间与重点监测阈值。"""

    temperature_comfort_min_c: float = Field(default=22.0, ge=10.0, le=35.0)
    temperature_comfort_max_c: float = Field(default=26.0, ge=10.0, le=35.0)
    humidity_comfort_min_percent: float = Field(default=40.0, ge=0.0, le=100.0)
    humidity_comfort_max_percent: float = Field(default=60.0, ge=0.0, le=100.0)
    temperature_warning_low_c: float = Field(default=20.0, ge=0.0, le=40.0)
    temperature_warning_high_c: float = Field(default=28.0, ge=0.0, le=45.0)
    humidity_warning_low_percent: float = Field(default=35.0, ge=0.0, le=100.0)
    humidity_warning_high_percent: float = Field(default=70.0, ge=0.0, le=100.0)
    updated_at_ms: int = Field(default_factory=now_ms)

    @model_validator(mode="after")
    def validate_ranges(self):
        if self.temperature_comfort_min_c > self.temperature_comfort_max_c:
            raise ValueError("适宜温度下限不能高于适宜温度上限")
        if self.humidity_comfort_min_percent > self.humidity_comfort_max_percent:
            raise ValueError("适宜湿度下限不能高于适宜湿度上限")
        if self.temperature_warning_low_c > self.temperature_warning_high_c:
            raise ValueError("重点监测低温不能高于重点监测高温")
        if self.humidity_warning_low_percent > self.humidity_warning_high_percent:
            raise ValueError("重点监测低湿不能高于重点监测高湿")
        if self.temperature_warning_low_c > self.temperature_comfort_min_c:
            raise ValueError("重点监测低温需小于或等于适宜温度下限")
        if self.temperature_warning_high_c < self.temperature_comfort_max_c:
            raise ValueError("重点监测高温需大于或等于适宜温度上限")
        if self.humidity_warning_low_percent > self.humidity_comfort_min_percent:
            raise ValueError("重点监测低湿需小于或等于适宜湿度下限")
        if self.humidity_warning_high_percent < self.humidity_comfort_max_percent:
            raise ValueError("重点监测高湿需大于或等于适宜湿度上限")
        return self


class EnvironmentComfortAssessment(BaseModel):
    comfort_status: ComfortStatus
    alert_level: EnvironmentAlertLevel
    reason: str
    suggested_action: str


def assess_environment_comfort(
    temperature_c: float,
    humidity_percent: float,
    settings: EnvironmentThresholdSettings | None = None,
) -> EnvironmentComfortAssessment:
    """按用户阈值判断当前温湿度是否适宜。"""

    thresholds = settings or EnvironmentThresholdSettings()
    temp_state = _temperature_state(temperature_c, thresholds)
    humidity_state = _humidity_state(humidity_percent, thresholds)
    status = _merge_status(temp_state, humidity_state)
    alert_level = _alert_level(temperature_c, humidity_percent, thresholds, status)
    reason = _reason_text(temperature_c, humidity_percent, thresholds, temp_state, humidity_state, status, alert_level)
    suggested_action = _suggested_action(status, alert_level)
    return EnvironmentComfortAssessment(
        comfort_status=status,
        alert_level=alert_level,
        reason=reason,
        suggested_action=suggested_action,
    )


def _temperature_state(temperature_c: float, thresholds: EnvironmentThresholdSettings) -> ComfortStatus | None:
    if temperature_c < thresholds.temperature_comfort_min_c:
        return "cold"
    if temperature_c > thresholds.temperature_comfort_max_c:
        return "hot"
    return None


def _humidity_state(humidity_percent: float, thresholds: EnvironmentThresholdSettings) -> ComfortStatus | None:
    if humidity_percent < thresholds.humidity_comfort_min_percent:
        return "dry"
    if humidity_percent > thresholds.humidity_comfort_max_percent:
        return "humid"
    return None


def _merge_status(temp_state: ComfortStatus | None, humidity_state: ComfortStatus | None) -> ComfortStatus:
    if temp_state and humidity_state:
        return "mixed"
    if humidity_state:
        return humidity_state
    if temp_state:
        return temp_state
    return "comfortable"


def _alert_level(
    temperature_c: float,
    humidity_percent: float,
    thresholds: EnvironmentThresholdSettings,
    status: ComfortStatus,
) -> EnvironmentAlertLevel:
    if status == "comfortable":
        return "none"
    if (
        temperature_c <= thresholds.temperature_warning_low_c
        or temperature_c >= thresholds.temperature_warning_high_c
        or humidity_percent <= thresholds.humidity_warning_low_percent
        or humidity_percent >= thresholds.humidity_warning_high_percent
    ):
        return "warning"
    if status != "comfortable":
        return "watch"
    return "none"


def _reason_text(
    temperature_c: float,
    humidity_percent: float,
    thresholds: EnvironmentThresholdSettings,
    temp_state: ComfortStatus | None,
    humidity_state: ComfortStatus | None,
    status: ComfortStatus,
    alert_level: EnvironmentAlertLevel,
) -> str:
    current = f"当前温度 {temperature_c:.1f}°C、湿度 {humidity_percent:.0f}%"
    comfort_range = (
        f"{thresholds.temperature_comfort_min_c:.1f}-{thresholds.temperature_comfort_max_c:.1f}°C、"
        f"{thresholds.humidity_comfort_min_percent:.0f}-{thresholds.humidity_comfort_max_percent:.0f}%"
    )
    comfort = f"你的适宜区间为 {comfort_range}"
    if status == "comfortable":
        return f"{current}，均在你的适宜区间内（{comfort_range}）。"

    facts: list[str] = []
    if temp_state == "cold":
        boundary = thresholds.temperature_warning_low_c if alert_level == "warning" else thresholds.temperature_comfort_min_c
        label = "重点监测低温阈值" if alert_level == "warning" and temperature_c <= thresholds.temperature_warning_low_c else "适宜温度下限"
        facts.append(f"温度低于{label} {boundary:.1f}°C")
    elif temp_state == "hot":
        boundary = thresholds.temperature_warning_high_c if alert_level == "warning" else thresholds.temperature_comfort_max_c
        label = "重点监测高温阈值" if alert_level == "warning" and temperature_c >= thresholds.temperature_warning_high_c else "适宜温度上限"
        facts.append(f"温度高于{label} {boundary:.1f}°C")

    if humidity_state == "dry":
        boundary = thresholds.humidity_warning_low_percent if alert_level == "warning" else thresholds.humidity_comfort_min_percent
        label = "重点监测低湿阈值" if alert_level == "warning" and humidity_percent <= thresholds.humidity_warning_low_percent else "适宜湿度下限"
        facts.append(f"湿度低于{label} {boundary:.0f}%")
    elif humidity_state == "humid":
        boundary = thresholds.humidity_warning_high_percent if alert_level == "warning" else thresholds.humidity_comfort_max_percent
        label = "重点监测高湿阈值" if alert_level == "warning" and humidity_percent >= thresholds.humidity_warning_high_percent else "适宜湿度上限"
        facts.append(f"湿度高于{label} {boundary:.0f}%")

    facts_text = "，".join(facts)
    return f"{current}，{facts_text}；{comfort}。"


def _suggested_action(status: ComfortStatus, alert_level: EnvironmentAlertLevel) -> str:
    if status == "comfortable":
        return "当前温湿度处在你的适宜区间，保持现有环境即可。"
    prefix = "已进入重点监测范围，" if alert_level == "warning" else "已偏离你的适宜区间，"
    if status == "dry":
        return f"环境{prefix}建议补水，并按体感考虑加湿或短暂通风。"
    if status == "humid":
        return f"环境{prefix}建议留意闷湿感，必要时通风或开启除湿。"
    if status == "hot":
        return f"环境{prefix}建议微调空调、降低热源影响或短暂通风。"
    if status == "cold":
        return f"环境{prefix}建议注意保暖，并按体感微调空调温度。"
    return f"温湿度{prefix}建议先补水，再根据体感微调加湿、通风或空调。"
