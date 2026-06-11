from __future__ import annotations

from app.skills.hydration.schemas import HydrationInput, HydrationOutput
from app.skills.hydration_skill import HydrationAnalysisSkill


class HydrationSkillHandler:
    """饮水 Skill 运行时 handler，复用旧规则逻辑。"""

    def __init__(self, skill: HydrationAnalysisSkill | None = None) -> None:
        self.skill = skill or HydrationAnalysisSkill()

    def run(self, data: HydrationInput) -> HydrationOutput:
        """根据今日饮水量、饮水间隔和温湿度生成提醒建议。"""

        return self.skill.run(data)


def run(data: HydrationInput) -> HydrationOutput:
    return HydrationSkillHandler().run(data)
