"""饮水 Skill Package。"""

from app.skills.hydration.handler import HydrationSkillHandler, run
from app.skills.hydration.schemas import HydrationInput, HydrationOutput

__all__ = ["HydrationInput", "HydrationOutput", "HydrationSkillHandler", "run"]
