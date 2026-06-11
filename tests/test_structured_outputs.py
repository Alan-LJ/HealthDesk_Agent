import pytest
from pydantic import ValidationError

from app.graph.state import create_initial_agent_state
from app.schemas.agent_outputs import (
    DailyReportOutput,
    DeviceGuardianOutput,
    HealthAgentFinalOutput,
    PetActionOutput,
    RecommendationOutput,
)


def test_initial_agent_state_has_independent_defaults():
    state = create_initial_agent_state(task="分析当前办公健康状态", user_id="u1")

    assert state["task"] == "分析当前办公健康状态"
    assert state["user_id"] == "u1"
    assert state["runtime"] == "langgraph_deepseek"
    assert state["step_count"] == 0
    assert state["ai_context"] is None
    assert state["tool_calls"] == []
    assert state["observations"] == []
    assert state["stop_reason"] is None
    assert state["trace_id"]


def test_health_agent_final_output_validates_nested_pet_action():
    output = HealthAgentFinalOutput(
        task_type="office_health_check",
        risk_tags=["sedentary"],
        health_summary="连续坐姿时间偏长，建议做办公习惯层面的短暂活动。",
        recommendations=[
            RecommendationOutput(
                category="sedentary",
                risk_level="medium",
                reason="连续坐姿 75 分钟",
                suggested_action="站起活动 2 到 3 分钟",
                data_sources=["current_state"],
            )
        ],
        pet_action=PetActionOutput(
            emotion="concerned",
            animation="stretch",
            message="给你一个温和提醒：可以站起活动 2 到 3 分钟。",
            priority="medium",
            interruptible=True,
            reason="久坐风险达到中等提醒等级",
        ),
        confidence=0.8,
        data_sources_used=["current_state", "sedentary_skill"],
        tools_called=["get_current_state", "analyze_sedentary_risk"],
        guardrail_status={"output_guard": True},
        runtime="langgraph_deepseek",
        trace_id="trace-1",
        stop_reason="final_schema_valid_stop",
    )

    assert output.pet_action is not None
    assert output.pet_action.animation == "stretch"
    assert output.recommendations[0].risk_level == "medium"


def test_health_agent_final_output_rejects_empty_summary():
    with pytest.raises(ValidationError):
        HealthAgentFinalOutput(
            task_type="office_health_check",
            health_summary=" ",
            runtime="langgraph_deepseek",
            trace_id="trace-1",
            stop_reason="final_schema_valid_stop",
        )


def test_device_guardian_and_daily_report_outputs_validate():
    device = DeviceGuardianOutput(
        system_status="degraded",
        degraded_modules=["vital_sensor"],
        impact="生命体征趋势只能作为参考",
        advice_constraints=["不要基于低置信度生命体征生成强提醒"],
        user_message="部分设备数据可信度不足，相关建议已降级。",
        confidence=0.4,
    )
    report = DailyReportOutput(
        report_title="2026-06-08 办公健康日报",
        summary="今日状态基于已有模拟事件汇总。",
        key_findings=["记录到一次久坐提醒"],
        suggestions=["明天提前安排短暂起身活动"],
        tomorrow_focus=["久坐提醒"],
        data_sources_used=["today_summary", "event_log"],
    )

    assert device.system_status == "degraded"
    assert report.data_sources_used == ["today_summary", "event_log"]
