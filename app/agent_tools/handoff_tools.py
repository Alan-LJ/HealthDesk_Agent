from __future__ import annotations

from typing import Any

from app.agent_tools.local_tool import LocalToolBinding, make_tool
from app.agent_tools.tool_schemas import DeviceGuardianHandoffInput, ToolObservation
from app.skills import load_skill_markdown
from app.skills.device_guardian import DeviceGuardianInput, DeviceGuardianSkillHandler
from app.storage.repository import HealthRepository


def handoff_to_device_guardian_handler(repo: HealthRepository, data: DeviceGuardianHandoffInput) -> ToolObservation:
    """模型可触发的设备守护专家 handoff。"""

    current_state = repo.get_current_state()
    sensor_health = repo.get_sensor_health()
    device_confidence = current_state.device_confidence if current_state else 0.0
    result = DeviceGuardianSkillHandler().run(
        DeviceGuardianInput(
            sensor_health=sensor_health,
            device_confidence=device_confidence,
        )
    )
    return ToolObservation(
        tool_name="handoff_to_device_guardian",
        summary=f"DeviceGuardianAgent 返回: {result.system_status}；{result.impact}",
        raw_data=result.model_dump(),
        metadata={
            "handoff": "HealthCoordinatorAgent -> DeviceGuardianAgent",
            "user_id": data.user_id,
            "reason": data.reason,
            "source": "model_triggered_handoff",
        },
    )


def build_handoff_tools(repo: HealthRepository) -> list[LocalToolBinding[Any]]:
    device_doc = load_skill_markdown("device_guardian")
    return [
        make_tool(
            name="handoff_to_device_guardian",
            description=(
                "模型可触发的专家 Agent handoff：HealthCoordinatorAgent -> DeviceGuardianAgent。"
                "当设备置信度偏低、sensor_health 异常、或建议需要降级时调用。"
                "该 handoff 会读取 SQLite 当前设备状态并返回降级约束，不是 Python 路由。\n\n"
                f"{device_doc}"
            ),
            args_schema=DeviceGuardianHandoffInput,
            func=lambda data: handoff_to_device_guardian_handler(repo, data),
        )
    ]
