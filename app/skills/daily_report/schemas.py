"""日报 Skill 的输入输出模型。"""

from app.schemas.agent_outputs import DailyReportOutput
from app.skills.daily_report_skill import DailyReportInput

__all__ = ["DailyReportInput", "DailyReportOutput"]
