import json

from langchain_core.messages import AIMessage

from app.agent_runtimes.base import AgentRunRequest
from app.agent_runtimes.langgraph_deepseek_runtime import LangGraphDeepSeekRuntime
from app.agent_runtimes.settings import AgentRuntimeSettings
from app.simulation.simulator import HealthSimulator
from app.storage.db import connect
from app.storage.repository import HealthRepository


class FakeToolCallingDeepSeek:
    """测试用模型替身：只模拟 DeepSeek 返回 tool_calls，不参与业务规则。"""

    def __init__(self, decisions: list[dict]) -> None:
        self.decisions = list(decisions)
        self.bound_tool_names: list[str] = []
        self.messages_seen: list[list] = []

    def bind_tools(self, tools):
        self.bound_tool_names = [tool.name for tool in tools]
        return self

    def invoke(self, messages):
        self.messages_seen.append(list(messages))
        decision = self.decisions.pop(0)
        if decision["type"] == "tool":
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": decision["name"],
                        "args": decision.get("args", {}),
                        "id": decision.get("id", decision["name"]),
                    }
                ],
            )
        return AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "submit_final_output",
                    "args": _final_args(decision["summary"]),
                    "id": "final-output",
                }
            ],
        )


def _repo_with_tick(tmp_path, scenario: str) -> HealthRepository:
    repo = HealthRepository(tmp_path / f"{scenario}.db")
    tick = HealthSimulator(scenario).tick()
    repo.save_tick(tick.raw, tick.feature, tick.state, tick.events, tick.sensor_health)
    return repo


def _settings() -> AgentRuntimeSettings:
    return AgentRuntimeSettings(
        deepseek_api_key="unit-test-key",
        max_agent_steps=6,
        max_same_tool_calls=2,
        trace_to_sqlite=True,
    )


def _final_args(summary: str) -> dict:
    return {
        "task_type": "office_health_check",
        "risk_tags": [],
        "health_summary": summary,
        "recommendations": [],
        "pet_action": None,
        "confidence": 0.82,
        "data_sources_used": ["ai_context"],
        "tools_called": [],
        "guardrail_status": {"input_guard": True},
        "runtime": "langgraph_deepseek",
        "trace_id": "filled-by-runtime",
        "stop_reason": "final_schema_valid_stop",
    }


def test_langgraph_deepseek_runtime_executes_model_selected_tools_and_final_output(tmp_path):
    repo = _repo_with_tick(tmp_path, "sedentary_high")
    fake_model = FakeToolCallingDeepSeek(
        [
            {"type": "tool", "name": "get_current_state", "args": {"user_id": "default"}},
            {
                "type": "tool",
                "name": "analyze_sedentary_risk",
                "args": {"sedentary_minutes": 96, "posture_change_level": "low", "device_confidence": 0.95},
            },
            {"type": "final", "summary": "模型基于状态工具和久坐分析提交结构化输出。"},
        ]
    )
    runtime = LangGraphDeepSeekRuntime(repo=repo, settings=_settings(), chat_model=fake_model)

    result = runtime.run(AgentRunRequest(task="分析当前久坐状态"))

    assert result.runtime == "langgraph_deepseek"
    assert result.final_output["runtime"] == "langgraph_deepseek"
    assert result.final_output["trace_id"] == result.trace_id
    assert result.stop_reason == "final_schema_valid_stop"
    assert result.metadata["tools_called"] == ["get_current_state", "analyze_sedentary_risk"]
    assert result.metadata["observation_count"] == 2
    assert "submit_final_output" in fake_model.bound_tool_names
    assert "handoff_to_device_guardian" in fake_model.bound_tool_names

    with connect(repo.db_path) as conn:
        row = conn.execute("SELECT payload_json FROM agent_trace_log ORDER BY id DESC LIMIT 1").fetchone()
    trace = json.loads(row["payload_json"])
    assert trace["runtime_kind"] == "langgraph_deepseek"
    assert trace["latency_ms"] >= 0
    assert trace["tool_calls"]
    assert trace["observations"]


def test_langgraph_deepseek_runtime_allows_model_triggered_handoff(tmp_path):
    repo = _repo_with_tick(tmp_path, "device_degraded")
    fake_model = FakeToolCallingDeepSeek(
        [
            {"type": "tool", "name": "get_sensor_health", "args": {"user_id": "default"}},
            {
                "type": "tool",
                "name": "handoff_to_device_guardian",
                "args": {"user_id": "default", "reason": "sensor_health 显示设备降级"},
            },
            {"type": "final", "summary": "模型触发设备守护专家 handoff 后提交结构化输出。"},
        ]
    )
    runtime = LangGraphDeepSeekRuntime(repo=repo, settings=_settings(), chat_model=fake_model)

    result = runtime.run(AgentRunRequest(task="分析设备可信度"))

    assert result.metadata["handoffs_called"] == ["handoff_to_device_guardian"]
    assert "device" in result.final_output["risk_tags"]
    assert result.metadata["guardrail_status"]["observation_guard"] is True


def test_langgraph_deepseek_runtime_provides_capability_context_for_direct_answer(tmp_path):
    repo = _repo_with_tick(tmp_path, "normal_work")
    fake_model = FakeToolCallingDeepSeek(
        [
            {"type": "final", "summary": "我可以读取办公健康上下文、调用健康分析工具，并通过结构化输出生成桌宠提醒。"},
        ]
    )
    runtime = LangGraphDeepSeekRuntime(repo=repo, settings=_settings(), chat_model=fake_model)

    result = runtime.run(AgentRunRequest(task="你会哪些功能呢？"))

    system_text = fake_model.messages_seen[0][0].content
    human_payload = json.loads(fake_model.messages_seen[0][1].content)
    assert "agent_capabilities" in human_payload
    assert human_payload["agent_capabilities"]["can_do"]
    assert "office_health_snapshot" in human_payload["ai_context"]
    assert human_payload["interaction_policy"]["persist_pet_action_by_default"] is False
    assert human_payload["interaction_policy"]["max_health_summary_chars"] == 220
    assert "current_datetime_local" in human_payload
    assert "agent_capabilities" in system_text
    assert "直接调用 submit_final_output" in system_text
    assert "analyze_office_health_snapshot" in system_text
    assert "AIContext.office_health_snapshot 已存在" in system_text
    assert "health_summary 必须是给用户看的最终答复" in system_text
    assert result.metadata["tools_called"] == []
    assert result.final_output["data_sources_used"] == ["ai_context"]


def test_same_real_runtime_can_follow_different_model_tool_sequences(tmp_path):
    sedentary_repo = _repo_with_tick(tmp_path, "sedentary_high")
    hydration_repo = _repo_with_tick(tmp_path, "low_hydration")
    sedentary_model = FakeToolCallingDeepSeek(
        [
            {
                "type": "tool",
                "name": "analyze_sedentary_risk",
                "args": {"sedentary_minutes": 96, "posture_change_level": "low", "device_confidence": 0.95},
            },
            {"type": "final", "summary": "久坐路径完成。"},
        ]
    )
    hydration_model = FakeToolCallingDeepSeek(
        [
            {
                "type": "tool",
                "name": "analyze_hydration_risk",
                "args": {
                    "drink_today_ml": 350,
                    "last_drink_minutes_ago": 160,
                    "humidity_percent": 38,
                    "temperature_c": 24,
                },
            },
            {"type": "final", "summary": "饮水路径完成。"},
        ]
    )

    sedentary = LangGraphDeepSeekRuntime(repo=sedentary_repo, settings=_settings(), chat_model=sedentary_model).run(
        AgentRunRequest(task="分析久坐")
    )
    hydration = LangGraphDeepSeekRuntime(repo=hydration_repo, settings=_settings(), chat_model=hydration_model).run(
        AgentRunRequest(task="分析饮水")
    )

    assert sedentary.metadata["tools_called"] == ["analyze_sedentary_risk"]
    assert hydration.metadata["tools_called"] == ["analyze_hydration_risk"]
    assert sedentary.runtime == hydration.runtime == "langgraph_deepseek"
