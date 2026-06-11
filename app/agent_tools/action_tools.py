from __future__ import annotations

from typing import Any

from app.agent_tools.local_tool import LocalToolBinding, make_tool
from app.agent_tools.tool_schemas import SaveDailyReportInput, SavePetActionInput, ToolObservation
from app.skills import load_skill_markdown
from app.skills.daily_report import DailyReportInput, DailyReportSkillHandler
from app.skills.pet_dialogue import PetDialogueInput, PetDialogueSkillHandler
from app.storage.repository import HealthRepository


def create_pet_action_handler(data: PetDialogueInput) -> ToolObservation:
    action = PetDialogueSkillHandler().run(data)
    return ToolObservation(
        tool_name="create_pet_action",
        summary=f"生成桌宠动作 {action.animation}，优先级 {action.priority}。",
        raw_data=action.model_dump(),
        metadata={"skill": "pet_dialogue"},
    )


def save_pet_action_handler(repo: HealthRepository, data: SavePetActionInput) -> ToolObservation:
    repo.save_pet_action(data.action)
    return ToolObservation(
        tool_name="save_pet_action",
        summary=f"已保存桌宠动作 {data.action.animation}。",
        raw_data=data.action.model_dump(),
        metadata={"source": "sqlite_pet_action_log"},
    )


def save_daily_report_handler(repo: HealthRepository, data: SaveDailyReportInput) -> ToolObservation:
    repo.save_daily_report(data.report)
    return ToolObservation(
        tool_name="save_daily_report",
        summary="已保存日报 JSON。",
        raw_data={"report": data.report},
        metadata={"source": "sqlite_daily_report_log"},
    )


def create_daily_report_handler(data: DailyReportInput) -> ToolObservation:
    report = DailyReportSkillHandler().run(data)
    return ToolObservation(
        tool_name="create_daily_report",
        summary=f"生成日报: {report.report_title}",
        raw_data=report.model_dump(),
        metadata={"skill": "daily_report"},
    )


def build_action_tools(repo: HealthRepository) -> list[LocalToolBinding[Any]]:
    pet_doc = load_skill_markdown("pet_dialogue")
    report_doc = load_skill_markdown("daily_report")
    return [
        make_tool(
            name="create_pet_action",
            description=(
                "把风险标签和建议动作转换成安全、温和、可执行的桌宠动作。"
                "仅当当前 observation 没有提供 pet_action 且用户需要桌宠动作时调用；"
                "如果 analyze_office_health_snapshot 已返回 pet_action，不要重复调用本工具。"
                f"\n\n{pet_doc}"
            ),
            args_schema=PetDialogueInput,
            func=create_pet_action_handler,
        ),
        make_tool(
            name="create_daily_report",
            description=f"根据 today_summary、recent_events 和 memory_summary 生成日报，不得编造统计。\n\n{report_doc}",
            args_schema=DailyReportInput,
            func=create_daily_report_handler,
        ),
        make_tool(
            name="save_pet_action",
            description="仅当用户明确要求保存或记录桌宠动作时调用；普通网页版交互只返回 final_output，不要默认保存。",
            args_schema=SavePetActionInput,
            func=lambda data: save_pet_action_handler(repo, data),
        ),
        make_tool(
            name="save_daily_report",
            description="仅当用户明确要求保存日报时调用。日报内容必须已经通过结构化校验。",
            args_schema=SaveDailyReportInput,
            func=lambda data: save_daily_report_handler(repo, data),
        ),
    ]
