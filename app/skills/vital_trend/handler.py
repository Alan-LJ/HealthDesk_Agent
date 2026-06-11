from __future__ import annotations

from app.skills.vital_trend.schemas import VitalTrendInput, VitalTrendOutput
from app.skills.vital_trend_skill import VitalTrendSkill


class VitalTrendSkillHandler:
    """生命体征趋势 Skill 运行时 handler，复用旧安全规则。"""

    def __init__(self, skill: VitalTrendSkill | None = None) -> None:
        self.skill = skill or VitalTrendSkill()

    def run(self, data: VitalTrendInput) -> VitalTrendOutput:
        """只生成办公趋势参考，不生成医疗判断。"""

        return self.skill.run(data)


def run(data: VitalTrendInput) -> VitalTrendOutput:
    return VitalTrendSkillHandler().run(data)
