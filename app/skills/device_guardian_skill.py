from __future__ import annotations

from pydantic import BaseModel

from app.schemas.agent_outputs import DeviceGuardianOutput
from app.schemas.common import SensorHealth


class DeviceGuardianInput(BaseModel):
    sensor_health: list[SensorHealth]
    device_confidence: float
    last_seen_seconds: int = 0
    error_codes: list[str] = []


class DeviceGuardianSkill:
    """设备守护 Skill，解释哪些模拟传感器正在降级以及影响范围。"""

    def run(self, data: DeviceGuardianInput) -> DeviceGuardianOutput:
        degraded = [item.module for item in data.sensor_health if not item.online or item.confidence < 0.6]
        if not degraded and data.device_confidence >= 0.6:
            return DeviceGuardianOutput(system_status="healthy", degraded_modules=[], impact="所有模拟模块处于可用状态", user_message="设备数据可信度正常")
        impact = "；".join([f"{module} 相关建议需要降级为参考" for module in degraded]) or "整体设备置信度偏低"
        return DeviceGuardianOutput(system_status="degraded", degraded_modules=degraded, impact=impact, user_message="部分设备数据可信度不足，Agent 不会基于这些数据输出强结论")
