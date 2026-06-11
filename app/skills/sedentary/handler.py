from __future__ import annotations

from app.skills.sedentary.schemas import SedentaryInput, SedentaryOutput
from app.skills.sedentary_skill import SedentaryAnalysisSkill


class SedentarySkillHandler:
    """久坐 Skill 运行时 handler。

    handler 是 Agent tool 真正调用的执行层。这里先复用旧规则实现，后续
    LangGraph tool binding 会读取 SKILL.md 的说明，再调用本 handler。
    """

    def __init__(self, skill: SedentaryAnalysisSkill | None = None) -> None:
        self.skill = skill or SedentaryAnalysisSkill()

    def run(self, data: SedentaryInput) -> SedentaryOutput:
        """根据久坐分钟数、坐姿变化和设备置信度输出风险判断。"""

        return self.skill.run(data)


def run(data: SedentaryInput) -> SedentaryOutput:
    """便捷函数，供后续 tool binding 直接调用。"""

    return SedentarySkillHandler().run(data)
