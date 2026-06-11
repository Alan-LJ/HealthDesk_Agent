"""桌宠话术 Skill 的输入模型。输出沿用 PetAction。"""

from app.schemas.event import PetAction
from app.skills.pet_dialogue_skill import PetDialogueInput

__all__ = ["PetDialogueInput", "PetAction"]
