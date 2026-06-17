from __future__ import annotations

from typing import Any

from app.agent_tools.local_tool import LocalToolBinding, make_tool
from app.agent_tools.tool_schemas import ToolObservation
from app.skills import load_skill_markdown
from app.skills.web_realtime import WeatherInput, WebRealtimeSkillHandler, WebSearchInput


def _skill_description(short: str) -> str:
    markdown = load_skill_markdown("web_realtime")
    return f"{short}\n\n以下是该 Skill 的能力说明书，请遵守其中的触发条件、输入输出和禁止事项：\n{markdown}"


def get_weather_handler(handler: WebRealtimeSkillHandler, data: WeatherInput) -> ToolObservation:
    result = handler.get_weather(data)
    return ToolObservation(
        tool_name="get_weather",
        success=True,
        summary=result.summary,
        raw_data=result.model_dump(),
        metadata={
            "skill": "web_realtime",
            "status": result.status,
            "data_sources": result.data_sources,
            "realtime_boundary": "weather_and_air_quality_only",
        },
    )


def search_web_handler(handler: WebRealtimeSkillHandler, data: WebSearchInput) -> ToolObservation:
    result = handler.search_web(data)
    return ToolObservation(
        tool_name="search_web",
        success=True,
        summary=result.summary,
        raw_data=result.model_dump(),
        metadata={
            "skill": "web_realtime",
            "status": result.status,
            "provider": result.provider,
            "data_sources": result.data_sources,
            "realtime_boundary": "must_report_unavailable_when_provider_is_not_configured",
        },
    )


def build_realtime_tools(handler: WebRealtimeSkillHandler | None = None) -> list[LocalToolBinding[Any]]:
    runtime_handler = handler or WebRealtimeSkillHandler()
    return [
        make_tool(
            name="get_weather",
            description=_skill_description(
                "查询某个地点的实时天气和空气质量。天气、温湿度、PM2.5、AQI、紫外线等外部实时信息优先使用本工具。"
            ),
            args_schema=WeatherInput,
            func=lambda data: get_weather_handler(runtime_handler, data),
        ),
        make_tool(
            name="search_web",
            description=_skill_description(
                "通用网页搜索工具。只有当问题依赖本地数据/RAG 无法覆盖的外部实时网页信息时调用；天气问题优先调用 get_weather。"
            ),
            args_schema=WebSearchInput,
            func=lambda data: search_web_handler(runtime_handler, data),
        ),
    ]
