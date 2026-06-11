from __future__ import annotations

from app.schemas.agent_outputs import DailyReportOutput
from app.skills.daily_report.schemas import DailyReportInput
from app.skills.daily_report_skill import DailyReportSkill


class DailyReportSkillHandler:
    """日报 Skill 运行时 handler，复用旧日报生成规则。"""

    def __init__(self, skill: DailyReportSkill | None = None) -> None:
        self.skill = skill or DailyReportSkill()

    def run(self, data: DailyReportInput) -> DailyReportOutput:
        """只基于今日统计、近期事件和 memory summary 生成日报。"""

        return self.skill.run(data)


def run(data: DailyReportInput) -> DailyReportOutput:
    return DailyReportSkillHandler().run(data)
