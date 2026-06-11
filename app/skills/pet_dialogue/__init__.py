"""桌宠话术 Skill Package。"""

from app.skills.pet_dialogue.handler import PetDialogueSkillHandler, run
from app.skills.pet_dialogue.schemas import PetDialogueInput

__all__ = ["PetDialogueInput", "PetDialogueSkillHandler", "run"]
