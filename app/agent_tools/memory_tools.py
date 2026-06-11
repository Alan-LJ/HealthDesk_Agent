from __future__ import annotations

from typing import Any

from app.agent_tools.local_tool import LocalToolBinding, make_tool
from app.agent_tools.tool_schemas import GetMemorySummaryInput, ToolObservation, UpdateUserMemoryInput
from app.storage.repository import HealthRepository


def update_user_memory_handler(repo: HealthRepository, data: UpdateUserMemoryInput) -> ToolObservation:
    """更新用户摘要记忆。

    本阶段 memory 是规则摘要和 SQLite 持久化，后续可以接入更完整的滑动窗口与压缩策略。
    """

    repo.save_memory(data.summary)
    return ToolObservation(
        tool_name="update_user_memory",
        summary=f"已更新用户 {data.user_id} 的 memory summary。",
        raw_data={"memory_summary": data.summary},
        metadata={"user_id": data.user_id, "source": "sqlite_memory_log"},
    )


def get_user_profile_handler(data: GetMemorySummaryInput) -> ToolObservation:
    """返回简化用户画像。

    当前用户画像还没有独立表，先返回默认偏好，后续可扩展为 SQLite 持久化画像。
    """

    return ToolObservation(
        tool_name="get_user_profile",
        summary="读取默认用户画像：温和语气，提醒冷却 30 分钟。",
        raw_data={"user_id": data.user_id, "preferred_tone": "gentle", "reminder_cooldown_minutes": 30},
        metadata={"source": "default_profile"},
    )


def summarize_recent_interactions_handler(repo: HealthRepository, data: GetMemorySummaryInput) -> ToolObservation:
    events = repo.get_recent_events(20)
    event_types = [event.event_type for event in events]
    summary = "；".join(sorted(set(event_types))) if event_types else "暂无近期交互。"
    return ToolObservation(
        tool_name="summarize_recent_interactions",
        summary=summary,
        raw_data={"event_types": event_types},
        metadata={"user_id": data.user_id, "source": "sqlite_event_log"},
    )


def build_memory_tools(repo: HealthRepository) -> list[LocalToolBinding[Any]]:
    return [
        make_tool(
            name="update_user_memory",
            description="仅当用户明确要求记录偏好、更新记忆或保存长期模式时调用。普通网页版交互不要默认更新 memory。",
            args_schema=UpdateUserMemoryInput,
            func=lambda data: update_user_memory_handler(repo, data),
        ),
        make_tool(
            name="get_user_profile",
            description="读取用户提醒语气和提醒冷却等画像信息。",
            args_schema=GetMemorySummaryInput,
            func=get_user_profile_handler,
        ),
        make_tool(
            name="summarize_recent_interactions",
            description="根据近期事件生成交互摘要，用于 memory 更新或日报参考。",
            args_schema=GetMemorySummaryInput,
            func=lambda data: summarize_recent_interactions_handler(repo, data),
        ),
    ]
