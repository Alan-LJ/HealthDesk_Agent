from __future__ import annotations

from typing import Any

from app.agent_tools.analysis_tools import analyze_office_health_snapshot_handler
from app.agent_tools.tool_schemas import AnalyzeOfficeHealthSnapshotInput
from app.agent_tools.tool_registry import AgentToolRegistry
from app.graph.state import AgentState
from app.graph.trace_adapter import append_trace_step
from app.schemas.agent_outputs import HealthAgentFinalOutput, PetActionOutput, RecommendationOutput
from app.schemas.ai_context import AIContext
from app.storage.repository import HealthRepository


def load_context_node(state: AgentState, *, repo: HealthRepository) -> AgentState:
    """加载 AIContext。

    该节点负责把 SQLite 中的当前状态、近期事件、今日统计、设备健康和 memory
    组装到 AgentState。RAG 不在这里执行，后续必须通过 RAG tool 调用。
    """

    current_state = repo.get_current_state()
    if current_state is None:
        state.setdefault("errors", []).append("当前没有状态数据，请先运行 simulation tick。")
        return append_trace_step(
            state,
            node_name="load_context_node",
            action_type="load_context",
            observation_summary="加载失败：当前没有状态数据。",
            stop_reason="tool_error_stop",
        )
    context = AIContext(
        current_state=current_state,
        recent_events=repo.get_recent_events(10),
        today_summary=repo.today_summary(),
        sensor_health=repo.get_sensor_health(),
        memory_summary=repo.get_memory_summary(),
        retrieved_knowledge=[],
    )
    context_payload = context.model_dump()
    snapshot = analyze_office_health_snapshot_handler(repo, AnalyzeOfficeHealthSnapshotInput(user_id=state["user_id"]))
    if snapshot.success:
        context_payload["office_health_snapshot"] = snapshot.raw_data
        context_payload["office_health_snapshot_summary"] = snapshot.summary
    state["guardrail_status"] = {**state.get("guardrail_status", {}), "input_guard": True}
    state["ai_context"] = context_payload
    return append_trace_step(
        state,
        node_name="load_context_node",
        action_type="load_context",
        observation_summary="已从 SQLite 构建 AIContext。",
    )


def tool_execute_node(state: AgentState, *, registry: AgentToolRegistry) -> AgentState:
    """执行 pending tool call 并得到 observation。"""

    pending = state.get("pending_tool_call")
    if not pending:
        return state
    tool_name = pending["tool_name"]
    args = pending.get("tool_args", {})
    try:
        tool = registry.get(tool_name)
        observation = tool.invoke(args)
    except Exception as exc:
        state.setdefault("errors", []).append(f"{tool_name} 执行失败: {exc}")
        state["pending_tool_call"] = None
        return append_trace_step(
            state,
            node_name="tool_execute_node",
            action_type="tool_error",
            tool_name=tool_name,
            tool_args=args,
            observation_summary=str(exc),
            stop_reason="tool_error_stop",
        )
    state["last_observation"] = observation.model_dump()
    state.setdefault("tool_calls", []).append({"tool_name": tool_name, "tool_args": args})
    return append_trace_step(
        state,
        node_name="tool_execute_node",
        action_type="tool_result",
        tool_name=tool_name,
        tool_args=args,
        observation_summary=observation.summary,
    )


def observe_node(state: AgentState) -> AgentState:
    """把 observation 写回 AgentState，供下一轮 reason 节点读取。"""

    observation = state.get("last_observation")
    if not observation:
        return state
    state.setdefault("observations", []).append(observation)
    tool_name = observation.get("tool_name")
    raw_data = observation.get("raw_data") or {}
    if tool_name and tool_name.startswith("search_"):
        state.setdefault("retrieved_chunks", []).extend(raw_data.get("chunks", []))
    if tool_name == "analyze_office_health_snapshot":
        state.setdefault("risk_tags", [])
        for tag in raw_data.get("risk_tags", []):
            if tag not in state["risk_tags"]:
                state["risk_tags"].append(tag)
        analysis = dict(state.get("health_analysis") or {})
        analysis[tool_name] = raw_data
        state["health_analysis"] = analysis
        if raw_data.get("pet_action"):
            state["pet_action"] = raw_data["pet_action"]
    elif tool_name in {"analyze_sedentary_risk", "analyze_hydration_risk"}:
        if raw_data.get("risk_level") not in {None, "none"}:
            tag = "sedentary" if tool_name == "analyze_sedentary_risk" else "hydration"
            state.setdefault("risk_tags", [])
            if tag not in state["risk_tags"]:
                state["risk_tags"].append(tag)
        analysis = dict(state.get("health_analysis") or {})
        analysis[tool_name] = raw_data
        state["health_analysis"] = analysis
    elif tool_name == "analyze_environment_comfort":
        if raw_data.get("comfort_status") != "comfortable":
            state.setdefault("risk_tags", [])
            if "environment" not in state["risk_tags"]:
                state["risk_tags"].append("environment")
        analysis = dict(state.get("health_analysis") or {})
        analysis[tool_name] = raw_data
        state["health_analysis"] = analysis
    elif tool_name == "analyze_vital_trend":
        if raw_data.get("can_use_for_advice") is False:
            state.setdefault("risk_tags", [])
            if "device" not in state["risk_tags"]:
                state["risk_tags"].append("device")
        analysis = dict(state.get("health_analysis") or {})
        analysis[tool_name] = raw_data
        state["health_analysis"] = analysis
    elif tool_name in {"diagnose_device_health", "handoff_to_device_guardian"}:
        state["device_guardian_result"] = raw_data
        if raw_data.get("system_status") == "degraded":
            state.setdefault("risk_tags", [])
            if "device" not in state["risk_tags"]:
                state["risk_tags"].append("device")
    elif tool_name == "create_pet_action":
        state["pet_action"] = raw_data
    if not observation.get("success", True):
        state.setdefault("errors", []).append(observation.get("summary", "工具返回失败。"))
    state["pending_tool_call"] = None
    return append_trace_step(
        state,
        node_name="observe_node",
        action_type="observation",
        tool_name=tool_name,
        observation_summary=observation.get("summary", ""),
    )


def finalize_node(state: AgentState) -> AgentState:
    """生成并校验 HealthAgentFinalOutput。"""

    if state.get("final_output"):
        return state
    if state.get("errors"):
        summary = "Agent 运行未完成，已返回安全 fallback。"
        recommendations: list[RecommendationOutput] = []
        confidence = 0.2
    else:
        summary = _build_summary(state)
        recommendations = _build_recommendations(state)
        confidence = 0.8
    pet_action = None
    if state.get("pet_action"):
        raw = state["pet_action"]
        pet_action = PetActionOutput(
            emotion=raw.get("emotion", "calm"),
            animation=raw.get("animation", "idle"),
            message=raw.get("message", "当前状态已记录。"),
            priority=raw.get("priority", "low"),
            interruptible=True,
            reason="由 create_pet_action 工具生成。",
        )
    output = HealthAgentFinalOutput(
        task_type="office_health_check",
        risk_tags=state.get("risk_tags", []),
        health_summary=summary,
        recommendations=recommendations,
        pet_action=pet_action,
        confidence=confidence,
        data_sources_used=_data_sources_used(state),
        tools_called=[call.get("tool_name", "") for call in state.get("tool_calls", [])],
        guardrail_status=state.get("guardrail_status", {}),
        runtime=state["runtime"],
        trace_id=state["trace_id"],
        stop_reason=state.get("stop_reason") or "final_schema_valid_stop",
    )
    state["final_output"] = output.model_dump()
    state["stop_reason"] = output.stop_reason
    return append_trace_step(
        state,
        node_name="finalize_node",
        action_type="final",
        observation_summary="最终输出已通过 HealthAgentFinalOutput 校验。",
        stop_reason=state["stop_reason"],
    )


def guardrails_node(state: AgentState) -> AgentState:
    """执行简化 output/action guardrails。

    完整分阶段 guardrails 会在后续阶段扩展；这里先保证最终输出不含明显医疗化禁词。
    """

    banned = ["心率异常", "可能患病", "必须就医", "需要治疗", "诊断为", "有疾病风险"]
    text = str(state.get("final_output") or "")
    hits = [item for item in banned if item in text]
    status = dict(state.get("guardrail_status", {}))
    status["output_guard"] = not hits
    status["action_guard"] = not hits
    if hits:
        status["failed"] = True
        status["hits"] = hits
        state["stop_reason"] = "guardrail_fail_stop"
    state["guardrail_status"] = status
    if state.get("final_output"):
        final_output = dict(state["final_output"] or {})
        final_output["guardrail_status"] = status
        final_output["stop_reason"] = state.get("stop_reason") or final_output.get("stop_reason")
        state["final_output"] = final_output
    return append_trace_step(
        state,
        node_name="guardrails_node",
        action_type="guardrail_check",
        observation_summary="护栏通过。" if not hits else f"护栏命中: {hits}",
        stop_reason=state.get("stop_reason"),
    )


def save_trace_node(state: AgentState, *, repo: HealthRepository, trace_payload: dict[str, Any] | None = None) -> AgentState:
    """保存 trace 到 SQLite。"""

    state = append_trace_step(
        state,
        node_name="save_trace_node",
        action_type="save_trace",
        observation_summary="Agent trace 已保存。",
        stop_reason=state.get("stop_reason"),
    )
    if trace_payload is not None:
        trace_payload["steps"] = state.get("trace_steps", [])
        trace_payload["final_output"] = state.get("final_output") or {}
        trace_payload["guardrail_checks"] = state.get("guardrail_status", {})
        repo.save_trace(trace_payload)
    return state


def _build_summary(state: AgentState) -> str:
    if not state.get("risk_tags"):
        return "当前没有明显办公健康风险，继续保持当前节奏。"
    return "；".join([obs.get("summary", "") for obs in state.get("observations", []) if obs.get("summary")])[:300]


def _build_recommendations(state: AgentState) -> list[RecommendationOutput]:
    recommendations: list[RecommendationOutput] = []
    analysis = state.get("health_analysis") or {}
    for tool_name, data in analysis.items():
        if not isinstance(data, dict) or data.get("risk_level") in {None, "none"}:
            if tool_name == "analyze_office_health_snapshot":
                for item in data.get("recommendations", []):
                    recommendations.append(RecommendationOutput.model_validate(item))
            continue
        recommendations.append(
            RecommendationOutput(
                category=tool_name.replace("analyze_", "").replace("_risk", ""),
                risk_level=data.get("risk_level", "low"),
                reason=data.get("reason", "基于工具观察生成"),
                suggested_action=data.get("suggested_action", "保持当前节奏"),
                data_sources=[tool_name],
            )
        )
    return recommendations


def _data_sources_used(state: AgentState) -> list[str]:
    sources = {"ai_context"}
    for call in state.get("tool_calls", []):
        name = call.get("tool_name")
        if name:
            sources.add(name)
    if state.get("retrieved_chunks"):
        sources.add("rag")
    return sorted(sources)
