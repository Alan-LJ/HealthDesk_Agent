from __future__ import annotations

from pydantic import BaseModel


class EnvironmentInput(BaseModel):
    temperature_c: float
    humidity_percent: float


class EnvironmentOutput(BaseModel):
    comfort_status: str
    reason: str
    suggested_action: str


class EnvironmentComfortSkill:
    """环境舒适度 Skill，用温湿度规则生成非医疗化办公建议。"""

    def run(self, data: EnvironmentInput) -> EnvironmentOutput:
        if 22 <= data.temperature_c <= 26 and 40 <= data.humidity_percent <= 60:
            return EnvironmentOutput(comfort_status="comfortable", reason="温度和湿度处于办公舒适区间", suggested_action="保持当前环境")
        if data.humidity_percent < 35:
            return EnvironmentOutput(comfort_status="dry", reason=f"当前湿度 {data.humidity_percent:.0f}% 偏低", suggested_action="可以补水，必要时使用加湿或通风")
        if data.temperature_c > 28:
            return EnvironmentOutput(comfort_status="hot", reason=f"当前温度 {data.temperature_c:.1f} 摄氏度偏高", suggested_action="可以调整空调或短暂通风")
        if data.temperature_c < 20:
            return EnvironmentOutput(comfort_status="cold", reason=f"当前温度 {data.temperature_c:.1f} 摄氏度偏低", suggested_action="注意办公舒适度，可适当增添衣物或调整空调")
        return EnvironmentOutput(comfort_status="mixed", reason="温湿度有轻微偏离舒适区", suggested_action="根据体感微调办公环境")
