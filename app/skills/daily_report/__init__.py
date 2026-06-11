"""日报 Skill Package。"""

from app.skills.daily_report.handler import DailyReportSkillHandler, run
from app.skills.daily_report.schemas import DailyReportInput

__all__ = ["DailyReportInput", "DailyReportSkillHandler", "run"]
