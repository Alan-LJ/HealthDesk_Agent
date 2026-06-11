from __future__ import annotations

from app.skills.environment.schemas import EnvironmentInput, EnvironmentOutput
from app.skills.environment_skill import EnvironmentComfortSkill


class EnvironmentSkillHandler:
    """环境舒适度 Skill 运行时 handler，复用旧规则逻辑。"""

    def __init__(self, skill: EnvironmentComfortSkill | None = None) -> None:
        self.skill = skill or EnvironmentComfortSkill()

    def run(self, data: EnvironmentInput) -> EnvironmentOutput:
        """根据温度和湿度判断办公环境舒适度。"""

        return self.skill.run(data)


def run(data: EnvironmentInput) -> EnvironmentOutput:
    return EnvironmentSkillHandler().run(data)
