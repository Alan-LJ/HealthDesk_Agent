from __future__ import annotations

from app.schemas.common import SensorHealth
from app.schemas.event import EventData
from app.schemas.feature import FeatureData
from app.schemas.state import StateData


SCENARIOS = {
    "normal_work",
    "sedentary_high",
    "low_hydration",
    "dry_environment",
    "vital_low_confidence",
    "device_degraded",
    "mixed_risk",
}


def comfort_from_env(temperature_c: float, humidity_percent: float) -> str:
    """根据温湿度给出舒适度标签，规则保持简单，便于面试讲解。"""

    if temperature_c > 28 and humidity_percent < 35:
        return "mixed"
    if temperature_c > 28:
        return "hot"
    if temperature_c < 20:
        return "cold"
    if humidity_percent < 35:
        return "dry"
    if humidity_percent > 70:
        return "humid"
    return "comfortable"


def scenario_feature(name: str) -> FeatureData:
    """生成指定场景的 Feature Data。"""

    if name == "sedentary_high":
        return FeatureData(sedentary_minutes=96, posture_change_level="low", drink_today_ml=900, last_drink_minutes_ago=70)
    if name == "low_hydration":
        return FeatureData(sedentary_minutes=35, drink_today_ml=350, last_drink_minutes_ago=160, humidity_percent=38)
    if name == "dry_environment":
        return FeatureData(sedentary_minutes=30, drink_today_ml=800, last_drink_minutes_ago=60, temperature_c=29.0, humidity_percent=28)
    if name == "vital_low_confidence":
        return FeatureData(sedentary_minutes=42, drink_today_ml=700, last_drink_minutes_ago=90, breath_rate_bpm=18, heart_rate_bpm=86, vital_quality="low")
    if name == "device_degraded":
        return FeatureData(sedentary_minutes=75, posture_change_level="low", drink_today_ml=600, last_drink_minutes_ago=120, vital_quality="medium")
    if name == "mixed_risk":
        return FeatureData(
            sedentary_minutes=82,
            posture_change_level="low",
            drink_today_ml=320,
            last_drink_minutes_ago=180,
            temperature_c=29.5,
            humidity_percent=27,
            breath_rate_bpm=19,
            heart_rate_bpm=88,
            vital_quality="medium",
        )
    return FeatureData(sedentary_minutes=28, posture_change_level="medium", drink_today_ml=1000, last_drink_minutes_ago=35, breath_rate_bpm=16, heart_rate_bpm=76)


def feature_to_state(feature: FeatureData, device_confidence: float = 0.95) -> StateData:
    """把 Feature Data 转成当前 State Data。"""

    return StateData(
        sitting=feature.sitting,
        sedentary_minutes=feature.sedentary_minutes,
        posture_change_level=feature.posture_change_level,
        drink_today_ml=feature.drink_today_ml,
        last_drink_minutes_ago=feature.last_drink_minutes_ago,
        temperature_c=feature.temperature_c,
        humidity_percent=feature.humidity_percent,
        comfort_status=comfort_from_env(feature.temperature_c, feature.humidity_percent),
        breath_rate_bpm=feature.breath_rate_bpm,
        heart_rate_bpm=feature.heart_rate_bpm,
        vital_quality=feature.vital_quality,
        device_confidence=device_confidence,
    )


def scenario_sensor_health(name: str) -> list[SensorHealth]:
    """生成模拟设备健康状态。"""

    base = [
        SensorHealth(device_id="sim_seat_001", module="seat_pressure", confidence=0.95),
        SensorHealth(device_id="sim_cup_001", module="cup_weight", confidence=0.93),
        SensorHealth(device_id="sim_env_001", module="environment", confidence=0.96),
        SensorHealth(device_id="sim_vital_001", module="vital_trend", confidence=0.88),
    ]
    if name == "vital_low_confidence":
        base[-1] = SensorHealth(device_id="sim_vital_001", module="vital_trend", confidence=0.35, error_codes=["LOW_SIGNAL"])
    if name == "device_degraded":
        base[0] = SensorHealth(device_id="sim_seat_001", module="seat_pressure", online=False, confidence=0.25, last_seen_seconds=900, error_codes=["OFFLINE"])
    if name == "mixed_risk":
        base[-1] = SensorHealth(device_id="sim_vital_001", module="vital_trend", confidence=0.55, error_codes=["NOISY"])
    return base


def state_events(state: StateData, sensor_health: list[SensorHealth]) -> list[EventData]:
    """根据状态生成离散事件，供 Agent、日报和记忆使用。"""

    events: list[EventData] = []
    if state.sedentary_minutes >= 45:
        severity = "high" if state.sedentary_minutes > 90 else "medium" if state.sedentary_minutes >= 60 else "low"
        events.append(EventData(event_type="sedentary_warning", severity=severity, message=f"连续坐姿 {state.sedentary_minutes} 分钟"))
    if state.drink_today_ml < 600 and state.last_drink_minutes_ago >= 90:
        events.append(EventData(event_type="hydration_warning", severity="medium", message="今日饮水偏少且距离上次饮水较久"))
    if state.comfort_status != "comfortable":
        events.append(EventData(event_type="environment_warning", severity="medium", message=f"环境舒适度为 {state.comfort_status}"))
    if state.vital_quality != "low" and (state.breath_rate_bpm or state.heart_rate_bpm):
        events.append(EventData(event_type="vital_trend_update", severity="info", message="生命体征趋势数据已更新，仅作趋势参考"))
    for item in sensor_health:
        if not item.online or item.confidence < 0.6:
            events.append(EventData(event_type="device_degraded", severity="medium", message=f"{item.module} 数据可信度下降", payload=item.model_dump()))
    return events
