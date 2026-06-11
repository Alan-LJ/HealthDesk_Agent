from __future__ import annotations

from pydantic import BaseModel

from app.schemas.agent_outputs import DailyReportOutput
from app.schemas.common import TodaySummary
from app.schemas.event import EventData


class DailyReportInput(BaseModel):
    today_summary: TodaySummary
    recent_events: list[EventData]
    memory_summary: str = ""


class DailyReportSkill:
    """日报 Skill，只总结已有统计和事件，不编造数据。"""

    def run(self, data: DailyReportInput) -> DailyReportOutput:
        s = data.today_summary
        highlights = [
            f"今日记录到久坐提醒 {s.sedentary_warning_count} 次",
            f"今日记录到饮水提醒 {s.hydration_warning_count} 次",
            f"今日记录到环境提醒 {s.environment_warning_count} 次",
            f"当前累计饮水 {s.drink_total_ml} ml",
        ]
        suggestions: list[str] = []
        if s.sedentary_warning_count:
            suggestions.append("明天可以提前安排短暂起身活动")
        if s.hydration_warning_count:
            suggestions.append("明天可以把水杯放在更容易看到的位置")
        if s.environment_warning_count:
            suggestions.append("关注温湿度变化，优先改善办公舒适度")
        if not suggestions:
            suggestions.append("保持今天的办公节奏")
        return DailyReportOutput(
            report_title=f"{s.date} 办公健康日报",
            summary=data.memory_summary or "今日状态基于模拟数据生成，整体用于办公习惯参考",
            key_findings=highlights,
            suggestions=suggestions,
            tomorrow_focus=suggestions[:2],
            data_sources_used=["today_summary", "recent_events", "memory_summary"],
        )
