from __future__ import annotations

from typing import Any

from app.agent_tools.local_tool import LocalToolBinding, make_tool
from app.agent_tools.tool_schemas import AnalyzeOfficeHealthSnapshotInput, ToolObservation
from app.skills import load_skill_markdown
from app.skills.device_guardian import DeviceGuardianInput, DeviceGuardianSkillHandler
from app.skills.environment import EnvironmentInput, EnvironmentSkillHandler
from app.skills.hydration import HydrationInput, HydrationSkillHandler
from app.skills.pet_dialogue import PetDialogueInput, PetDialogueSkillHandler
from app.skills.sedentary import SedentaryInput, SedentarySkillHandler
from app.skills.vital_trend import VitalTrendInput, VitalTrendSkillHandler
from app.storage.repository import HealthRepository


def _skill_description(skill_name: str, short: str) -> str:
    """把 SKILL.md 纳入 tool description。

    这一步让 SKILL.md 进入模型可见工具说明，不只是放在目录里的文档。
    """

    markdown = load_skill_markdown(skill_name)
    return f"{short}\n\n以下是该 Skill 的能力说明书，请遵守其中的触发条件、输入输出和禁止事项：\n{markdown}"


def analyze_sedentary_risk_handler(data: SedentaryInput) -> ToolObservation:
    result = SedentarySkillHandler().run(data)
    return ToolObservation(
        tool_name="analyze_sedentary_risk",
        summary=f"久坐风险 {result.risk_level}；是否提醒: {result.should_remind}；原因: {result.reason}",
        raw_data=result.model_dump(),
        metadata={"skill": "sedentary"},
    )


def analyze_hydration_risk_handler(data: HydrationInput) -> ToolObservation:
    result = HydrationSkillHandler().run(data)
    return ToolObservation(
        tool_name="analyze_hydration_risk",
        summary=f"饮水风险 {result.risk_level}；是否提醒: {result.should_remind}；原因: {result.reason}",
        raw_data=result.model_dump(),
        metadata={"skill": "hydration"},
    )


def analyze_environment_comfort_handler(data: EnvironmentInput) -> ToolObservation:
    result = EnvironmentSkillHandler().run(data)
    return ToolObservation(
        tool_name="analyze_environment_comfort",
        summary=f"环境状态 {result.comfort_status}；原因: {result.reason}",
        raw_data=result.model_dump(),
        metadata={"skill": "environment"},
    )


def analyze_vital_trend_handler(data: VitalTrendInput) -> ToolObservation:
    result = VitalTrendSkillHandler().run(data)
    return ToolObservation(
        tool_name="analyze_vital_trend",
        summary=f"生命体征趋势参考: {result.trend_summary}；可用于建议: {result.can_use_for_advice}",
        raw_data=result.model_dump(),
        metadata={"skill": "vital_trend", "medical_boundary": "office_trend_only"},
    )


def diagnose_device_health_handler(data: DeviceGuardianInput) -> ToolObservation:
    result = DeviceGuardianSkillHandler().run(data)
    return ToolObservation(
        tool_name="diagnose_device_health",
        summary=f"设备状态 {result.system_status}；影响: {result.impact}",
        raw_data=result.model_dump(),
        metadata={"skill": "device_guardian"},
    )


def analyze_office_health_snapshot_handler(repo: HealthRepository, data: AnalyzeOfficeHealthSnapshotInput) -> ToolObservation:
    state = repo.get_current_state()
    if state is None:
        return ToolObservation(
            tool_name="analyze_office_health_snapshot",
            success=False,
            summary="当前没有状态数据，请先运行 simulation tick。",
            metadata={"user_id": data.user_id, "error": "state_not_found"},
        )

    sensor_health = repo.get_sensor_health()
    sedentary = SedentarySkillHandler().run(
        SedentaryInput(
            sedentary_minutes=state.sedentary_minutes,
            posture_change_level=state.posture_change_level,
            device_confidence=state.device_confidence,
        )
    )
    hydration = HydrationSkillHandler().run(
        HydrationInput(
            drink_today_ml=state.drink_today_ml,
            last_drink_minutes_ago=state.last_drink_minutes_ago,
            humidity_percent=state.humidity_percent,
            temperature_c=state.temperature_c,
        )
    )
    environment = EnvironmentSkillHandler().run(
        EnvironmentInput(temperature_c=state.temperature_c, humidity_percent=state.humidity_percent)
    )
    vital = VitalTrendSkillHandler().run(
        VitalTrendInput(
            breath_rate_bpm=state.breath_rate_bpm,
            heart_rate_bpm=state.heart_rate_bpm,
            vital_quality=state.vital_quality,
        )
    )
    device = DeviceGuardianSkillHandler().run(
        DeviceGuardianInput(sensor_health=sensor_health, device_confidence=state.device_confidence)
    )

    risk_tags: list[str] = []
    recommendations: list[dict[str, Any]] = []
    _append_risk_recommendation(
        recommendations,
        risk_tags,
        category="sedentary",
        risk_level=sedentary.risk_level,
        reason=sedentary.reason,
        suggested_action=sedentary.suggested_action,
    )
    _append_risk_recommendation(
        recommendations,
        risk_tags,
        category="hydration",
        risk_level=hydration.risk_level,
        reason=hydration.reason,
        suggested_action=hydration.suggested_action,
    )
    if environment.comfort_status != "comfortable":
        risk_tags.append("environment")
        recommendations.append(
            {
                "category": "environment",
                "risk_level": "medium",
                "reason": environment.reason,
                "suggested_action": environment.suggested_action,
                "data_sources": ["analyze_office_health_snapshot"],
            }
        )
    if not vital.can_use_for_advice:
        risk_tags.append("device")
    if device.system_status == "degraded":
        risk_tags.append("device")
        recommendations.append(
            {
                "category": "device",
                "risk_level": "medium",
                "reason": device.impact,
                "suggested_action": device.user_message,
                "data_sources": ["analyze_office_health_snapshot"],
            }
        )

    risk_tags = sorted(set(risk_tags))
    overall_risk = _overall_risk([item["risk_level"] for item in recommendations])
    suggested_action = recommendations[0]["suggested_action"] if recommendations else "当前没有明显办公健康风险，继续保持当前节奏"
    pet_action = None
    if data.include_pet_action:
        pet_action = PetDialogueSkillHandler().run(
            PetDialogueInput(
                risk_tags=risk_tags,
                risk_level=overall_risk,
                user_tone="gentle",
                suggested_action=suggested_action,
            )
        )

    summary_parts = [
        f"久坐 {sedentary.risk_level}: {sedentary.reason}",
        f"饮水 {hydration.risk_level}: {hydration.reason}",
        f"环境 {environment.comfort_status}: {environment.reason}",
        f"设备 {device.system_status}: {device.user_message}",
    ]
    return ToolObservation(
        tool_name="analyze_office_health_snapshot",
        summary="；".join(summary_parts),
        raw_data={
            "current_state": state.model_dump(),
            "analyses": {
                "sedentary": sedentary.model_dump(),
                "hydration": hydration.model_dump(),
                "environment": environment.model_dump(),
                "vital_trend": vital.model_dump(),
                "device_guardian": device.model_dump(),
            },
            "risk_tags": risk_tags,
            "overall_risk_level": overall_risk,
            "recommendations": recommendations,
            "pet_action": pet_action.model_dump() if pet_action else None,
        },
        metadata={"user_id": data.user_id, "source": "sqlite_state_log_and_skill_handlers", "fast_path": True},
    )


def _append_risk_recommendation(
    recommendations: list[dict[str, Any]],
    risk_tags: list[str],
    *,
    category: str,
    risk_level: str,
    reason: str,
    suggested_action: str,
) -> None:
    if risk_level == "none":
        return
    risk_tags.append(category)
    recommendations.append(
        {
            "category": category,
            "risk_level": risk_level,
            "reason": reason,
            "suggested_action": suggested_action,
            "data_sources": ["analyze_office_health_snapshot"],
        }
    )


def _overall_risk(levels: list[str]) -> str:
    order = {"none": 0, "low": 1, "medium": 2, "high": 3}
    if not levels:
        return "low"
    return max(levels, key=lambda item: order.get(item, 0))


def build_analysis_tools(repo: HealthRepository | None = None) -> list[LocalToolBinding[Any]]:
    """创建分析类工具绑定。"""

    tools: list[LocalToolBinding[Any]] = []
    if repo is not None:
        tools.append(
            make_tool(
                name="analyze_office_health_snapshot",
                description=(
                    "高频快路径：一次性读取当前 SQLite 办公健康状态，并综合分析久坐、饮水、环境舒适度、"
                    "生命体征趋势参考、设备可信度和桌宠动作建议。"
                    "当用户要求“分析当前办公健康状态”“生成桌宠提醒”“现在状态怎么样”等综合问题时，优先使用本工具，"
                    "避免分别调用 get_current_state、get_sensor_health 和多个 analyze_* 工具。"
                ),
                args_schema=AnalyzeOfficeHealthSnapshotInput,
                func=lambda data: analyze_office_health_snapshot_handler(repo, data),
            )
        )
    tools.extend(
        [
        make_tool(
            name="analyze_sedentary_risk",
            description=_skill_description("sedentary", "根据当前状态中的久坐分钟数、坐姿变化和设备置信度判断久坐风险。"),
            args_schema=SedentaryInput,
            func=analyze_sedentary_risk_handler,
        ),
        make_tool(
            name="analyze_hydration_risk",
            description=_skill_description("hydration", "根据今日饮水量、饮水间隔、温湿度判断饮水提醒等级。"),
            args_schema=HydrationInput,
            func=analyze_hydration_risk_handler,
        ),
        make_tool(
            name="analyze_environment_comfort",
            description=_skill_description("environment", "根据温度和湿度判断办公环境舒适度。"),
            args_schema=EnvironmentInput,
            func=analyze_environment_comfort_handler,
        ),
        make_tool(
            name="analyze_vital_trend",
            description=_skill_description("vital_trend", "只对呼吸和心率做办公趋势参考，不做医疗诊断。"),
            args_schema=VitalTrendInput,
            func=analyze_vital_trend_handler,
        ),
        make_tool(
            name="diagnose_device_health",
            description=_skill_description("device_guardian", "根据 sensor_health 和 device_confidence 生成设备降级说明。"),
            args_schema=DeviceGuardianInput,
            func=diagnose_device_health_handler,
        ),
        ]
    )
    return tools
