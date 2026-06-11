from __future__ import annotations

from app.schemas.agent_outputs import DeviceGuardianOutput
from app.skills.device_guardian.schemas import DeviceGuardianInput
from app.skills.device_guardian_skill import DeviceGuardianSkill


class DeviceGuardianSkillHandler:
    """设备守护 Skill 运行时 handler，复用旧设备降级规则。"""

    def __init__(self, skill: DeviceGuardianSkill | None = None) -> None:
        self.skill = skill or DeviceGuardianSkill()

    def run(self, data: DeviceGuardianInput) -> DeviceGuardianOutput:
        """根据传感器在线状态和置信度生成降级说明。"""

        return self.skill.run(data)


def run(data: DeviceGuardianInput) -> DeviceGuardianOutput:
    return DeviceGuardianSkillHandler().run(data)
