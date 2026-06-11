"""久坐 Skill Package。"""

from app.skills.sedentary.handler import SedentarySkillHandler, run
from app.skills.sedentary.schemas import SedentaryInput, SedentaryOutput

__all__ = ["SedentaryInput", "SedentaryOutput", "SedentarySkillHandler", "run"]
