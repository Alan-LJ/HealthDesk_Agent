"""生命体征趋势 Skill Package。"""

from app.skills.vital_trend.handler import VitalTrendSkillHandler, run
from app.skills.vital_trend.schemas import VitalTrendInput, VitalTrendOutput

__all__ = ["VitalTrendInput", "VitalTrendOutput", "VitalTrendSkillHandler", "run"]
