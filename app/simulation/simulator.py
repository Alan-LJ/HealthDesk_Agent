from __future__ import annotations

from dataclasses import dataclass

from app.schemas.common import Quality
from app.schemas.environment import EnvironmentThresholdSettings
from app.schemas.raw import RawData
from app.simulation.scenarios import SCENARIOS, feature_to_state, scenario_feature, scenario_sensor_health, state_events


@dataclass
class SimulationTick:
    """一次模拟 tick 的完整输出，包含 Raw/Feature/State/Event/SensorHealth。"""

    scenario_name: str
    raw: list[RawData]
    feature: object
    state: object
    events: list[object]
    sensor_health: list[object]


class HealthSimulator:
    """
    健康状态模拟器。

    当前项目不连接真实硬件，因此模拟器扮演“数据入口”。后续接入硬件时，可以保留
    下游 Schema、Agent、API，只替换这里的数据来源。
    """

    def __init__(self, scenario_name: str = "normal_work") -> None:
        self.scenario_name = scenario_name
        self.seq = 0

    def set_scenario(self, scenario_name: str) -> None:
        """切换模拟场景，输入必须属于 SCENARIOS。"""

        if scenario_name not in SCENARIOS:
            raise ValueError(f"未知场景: {scenario_name}")
        self.scenario_name = scenario_name

    def tick(self, environment_settings: EnvironmentThresholdSettings | None = None) -> SimulationTick:
        """生成一次完整模拟数据，并自动推导事件。"""

        self.seq += 1
        feature = scenario_feature(self.scenario_name)
        sensor_health = scenario_sensor_health(self.scenario_name)
        device_confidence = min(item.confidence for item in sensor_health)
        state = feature_to_state(feature, device_confidence=device_confidence, environment_settings=environment_settings)
        raw = [
            RawData(
                source="seat_pressure",
                device_id="sim_seat_001",
                seq=self.seq,
                data={"pressure_sum": 7200 if state.sitting else 100, "posture_change_score": 0.12},
                quality=Quality(valid=device_confidence >= 0.6, confidence=device_confidence),
            ),
            RawData(
                source="environment",
                device_id="sim_env_001",
                seq=self.seq,
                data={"temperature_c": state.temperature_c, "humidity_percent": state.humidity_percent},
                quality=Quality(valid=True, confidence=0.96),
            ),
        ]
        events = state_events(state, sensor_health)
        return SimulationTick(self.scenario_name, raw, feature, state, events, sensor_health)
