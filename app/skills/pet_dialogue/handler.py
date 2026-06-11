from __future__ import annotations

from app.schemas.event import PetAction
from app.skills.pet_dialogue.schemas import PetDialogueInput
from app.skills.pet_dialogue_skill import PetDialogueSkill


class PetDialogueSkillHandler:
    """桌宠话术 Skill 运行时 handler，复用旧桌宠动作规则。"""

    def __init__(self, skill: PetDialogueSkill | None = None) -> None:
        self.skill = skill or PetDialogueSkill()

    def run(self, data: PetDialogueInput) -> PetAction:
        """把风险标签、风险等级和建议动作转成桌宠动作 JSON。"""

        return self.skill.run(data)


def run(data: PetDialogueInput) -> PetAction:
    return PetDialogueSkillHandler().run(data)
