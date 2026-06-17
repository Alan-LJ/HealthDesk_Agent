import pytest

from app.agent_tools import build_agent_tools
from app.agent_tools.local_tool import LocalToolBinding
from app.agent_runtimes.settings import AgentRuntimeSettings
from app.schemas.common import SensorHealth, TodaySummary
from app.schemas.event import PetAction
from app.simulation.simulator import HealthSimulator
from app.storage.repository import HealthRepository


def _repo_with_tick(tmp_path, scenario: str = "mixed_risk") -> HealthRepository:
    repo = HealthRepository(tmp_path / "tools.db")
    simulator = HealthSimulator(scenario)
    tick = simulator.tick()
    repo.save_tick(tick.raw, tick.feature, tick.state, tick.events, tick.sensor_health)
    return repo


def _settings(tmp_path) -> AgentRuntimeSettings:
    return AgentRuntimeSettings(rag_backend="auto", rag_chroma_path=str(tmp_path / "chroma"))


def test_agent_tool_registry_contains_required_tools(tmp_path):
    repo = _repo_with_tick(tmp_path)
    registry = build_agent_tools(repo, settings=_settings(tmp_path))

    expected = {
        "get_current_state",
        "get_recent_events",
        "get_today_summary",
        "get_sensor_health",
        "get_memory_summary",
        "get_weather",
        "search_web",
        "search_health_knowledge",
        "search_pet_templates",
        "search_device_docs",
        "analyze_office_health_snapshot",
        "analyze_sedentary_risk",
        "analyze_hydration_risk",
        "analyze_environment_comfort",
        "analyze_vital_trend",
        "diagnose_device_health",
        "create_pet_action",
        "create_daily_report",
        "save_pet_action",
        "save_daily_report",
        "update_user_memory",
        "get_user_profile",
        "summarize_recent_interactions",
    }

    assert expected.issubset(set(registry.names()))


def test_context_and_rag_tools_return_observations(tmp_path):
    repo = _repo_with_tick(tmp_path, "sedentary_high")
    registry = build_agent_tools(repo, settings=_settings(tmp_path))

    state_obs = registry.get("get_current_state").invoke({"user_id": "default"})
    rag_obs = registry.get("search_health_knowledge").invoke({"query": "久坐 饮水 环境", "top_k": 3})

    assert state_obs.success is True
    assert state_obs.raw_data["sedentary_minutes"] >= 0
    assert rag_obs.success is True
    assert len(rag_obs.raw_data["chunks"]) > 0
    assert "knowledge_only" in rag_obs.metadata["rag_boundary"]


def test_analysis_tools_call_skill_package_handlers(tmp_path):
    repo = _repo_with_tick(tmp_path)
    registry = build_agent_tools(repo, settings=_settings(tmp_path))

    sedentary = registry.get("analyze_sedentary_risk").invoke(
        {"sedentary_minutes": 95, "posture_change_level": "low", "device_confidence": 0.9}
    )
    hydration = registry.get("analyze_hydration_risk").invoke(
        {"drink_today_ml": 300, "last_drink_minutes_ago": 150, "humidity_percent": 25, "temperature_c": 29}
    )
    vital = registry.get("analyze_vital_trend").invoke({"vital_quality": "low"})
    snapshot = registry.get("analyze_office_health_snapshot").invoke({"user_id": "default"})

    assert sedentary.raw_data["risk_level"] == "high"
    assert hydration.raw_data["risk_level"] == "high"
    assert vital.raw_data["can_use_for_advice"] is False
    assert snapshot.success is True
    assert "analyses" in snapshot.raw_data
    assert "recommendations" in snapshot.raw_data
    assert snapshot.raw_data["pet_action"]


def test_skill_markdown_is_in_tool_description(tmp_path):
    repo = _repo_with_tick(tmp_path)
    registry = build_agent_tools(repo, settings=_settings(tmp_path))

    description = registry.get("analyze_vital_trend").description

    assert "Vital Trend Skill" in description
    assert "禁止事项" in description
    assert "心率异常" in description


def test_action_and_memory_tools(tmp_path):
    repo = _repo_with_tick(tmp_path)
    registry = build_agent_tools(repo, settings=_settings(tmp_path))

    pet_obs = registry.get("create_pet_action").invoke(
        {"risk_tags": ["hydration"], "risk_level": "medium", "user_tone": "gentle", "suggested_action": "喝几口水"}
    )
    assert pet_obs.raw_data["animation"] == "drink_water"

    action = PetAction.model_validate(pet_obs.raw_data)
    save_obs = registry.get("save_pet_action").invoke({"action": action.model_dump()})
    memory_obs = registry.get("update_user_memory").invoke({"user_id": "default", "summary": "用户偏好温和提醒"})
    memory_read = registry.get("get_memory_summary").invoke({"user_id": "default"})

    assert save_obs.success is True
    assert memory_obs.success is True
    assert "温和提醒" in memory_read.raw_data["memory_summary"]


def test_create_daily_report_tool(tmp_path):
    repo = _repo_with_tick(tmp_path)
    registry = build_agent_tools(repo, settings=_settings(tmp_path))

    report_obs = registry.get("create_daily_report").invoke(
        {
            "today_summary": TodaySummary(date="2026-06-08", sedentary_warning_count=1, drink_total_ml=500).model_dump(),
            "recent_events": [],
            "memory_summary": "今天下午有久坐提醒",
        }
    )

    assert "办公健康日报" in report_obs.raw_data["report_title"]
    assert report_obs.raw_data["suggestions"]


def test_local_tool_to_langchain_tool_requires_dependency_when_missing():
    tool = LocalToolBinding(
        name="example",
        description="example",
        args_schema=TodaySummary,
        func=lambda data: data.model_dump(),
    )

    try:
        import langchain_core  # noqa: F401
    except ImportError:
        with pytest.raises(RuntimeError, match="langchain_core"):
            tool.to_langchain_tool()
