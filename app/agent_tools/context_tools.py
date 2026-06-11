from __future__ import annotations

from typing import Any

from app.agent_tools.local_tool import LocalToolBinding, make_tool
from app.agent_tools.tool_schemas import (
    GetCurrentStateInput,
    GetMemorySummaryInput,
    GetRecentEventsInput,
    GetSensorHealthInput,
    GetTodaySummaryInput,
    ToolObservation,
)
from app.storage.repository import HealthRepository


def get_current_state_handler(repo: HealthRepository, data: GetCurrentStateInput) -> ToolObservation:
    """读取当前办公健康状态。

    当前项目是单用户原型，user_id 暂时只进入 trace 和 metadata，不影响 SQLite 查询。
    """

    state = repo.get_current_state()
    if state is None:
        return ToolObservation(
            tool_name="get_current_state",
            success=False,
            summary="当前没有状态数据，请先运行 simulation tick。",
            metadata={"user_id": data.user_id, "error": "state_not_found"},
        )
    return ToolObservation(
        tool_name="get_current_state",
        summary=f"当前久坐 {state.sedentary_minutes} 分钟，饮水 {state.drink_today_ml} ml，设备置信度 {state.device_confidence:.2f}。",
        raw_data=state.model_dump(),
        metadata={"user_id": data.user_id, "source": "sqlite_state_log"},
    )


def get_recent_events_handler(repo: HealthRepository, data: GetRecentEventsInput) -> ToolObservation:
    events = repo.get_recent_events(data.limit)
    return ToolObservation(
        tool_name="get_recent_events",
        summary=f"读取到 {len(events)} 条近期事件。",
        raw_data={"events": [event.model_dump() for event in events]},
        metadata={"user_id": data.user_id, "limit": data.limit, "source": "sqlite_event_log"},
    )


def get_today_summary_handler(repo: HealthRepository, data: GetTodaySummaryInput) -> ToolObservation:
    summary = repo.today_summary()
    return ToolObservation(
        tool_name="get_today_summary",
        summary=f"今日久坐提醒 {summary.sedentary_warning_count} 次，饮水提醒 {summary.hydration_warning_count} 次。",
        raw_data=summary.model_dump(),
        metadata={"user_id": data.user_id, "source": "sqlite_event_log/state_log"},
    )


def get_sensor_health_handler(repo: HealthRepository, data: GetSensorHealthInput) -> ToolObservation:
    sensor_health = repo.get_sensor_health()
    degraded = [item.module for item in sensor_health if not item.online or item.confidence < 0.6]
    summary = "设备状态正常。" if not degraded else f"存在低可信或离线模块: {', '.join(degraded)}。"
    return ToolObservation(
        tool_name="get_sensor_health",
        summary=summary,
        raw_data={"sensor_health": [item.model_dump() for item in sensor_health]},
        metadata={"user_id": data.user_id, "source": "sqlite_kv_sensor_health"},
    )


def get_memory_summary_handler(repo: HealthRepository, data: GetMemorySummaryInput) -> ToolObservation:
    summary = repo.get_memory_summary()
    return ToolObservation(
        tool_name="get_memory_summary",
        summary=summary or "暂无用户记忆摘要。",
        raw_data={"memory_summary": summary},
        metadata={"user_id": data.user_id, "source": "sqlite_memory_log"},
    )


def build_context_tools(repo: HealthRepository) -> list[LocalToolBinding[Any]]:
    """创建上下文工具绑定。"""

    return [
        make_tool(
            name="get_current_state",
            description="读取用户当前办公健康状态。用户当前事实必须来自该工具或 AIContext，不能由 RAG 推断。",
            args_schema=GetCurrentStateInput,
            func=lambda data: get_current_state_handler(repo, data),
        ),
        make_tool(
            name="get_recent_events",
            description="读取近期事件日志，用于判断提醒历史、日报依据和 memory 更新。",
            args_schema=GetRecentEventsInput,
            func=lambda data: get_recent_events_handler(repo, data),
        ),
        make_tool(
            name="get_today_summary",
            description="读取今日统计摘要。日报和今日总结必须基于该工具返回的数据。",
            args_schema=GetTodaySummaryInput,
            func=lambda data: get_today_summary_handler(repo, data),
        ),
        make_tool(
            name="get_sensor_health",
            description="读取模拟传感器健康状态，用于判断低置信度和设备降级。",
            args_schema=GetSensorHealthInput,
            func=lambda data: get_sensor_health_handler(repo, data),
        ),
        make_tool(
            name="get_memory_summary",
            description="读取用户记忆摘要，例如提醒偏好、近期响应和历史风险模式。",
            args_schema=GetMemorySummaryInput,
            func=lambda data: get_memory_summary_handler(repo, data),
        ),
    ]
