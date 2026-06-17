from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ValidationError

from app.agent_runtimes.settings import AgentRuntimeSettings
from app.agent_tools.tool_registry import AgentToolRegistry
from app.graph.edges import no_new_information_hit, same_tool_limit_hit
from app.graph.nodes import finalize_node, guardrails_node, load_context_node, observe_node, save_trace_node, tool_execute_node
from app.graph.state import AgentState
from app.graph.trace_adapter import append_trace_step, build_trace_payload
from app.schemas.agent_outputs import HealthAgentFinalOutput
from app.schemas.common import now_ms
from app.storage.repository import HealthRepository


FINAL_OUTPUT_TOOL_NAME = "submit_final_output"

AGENT_CAPABILITIES: dict[str, Any] = {
    "identity": "HealthCoordinatorAgent，一个面向办公场景的健康桌宠 Agent。",
    "can_do": [
        "读取 AIContext 和 SQLite 中的当前办公状态，包括久坐、饮水、环境、设备置信度、近期事件和今日统计。",
        "按需调用真实工具分析久坐风险、饮水风险、环境舒适度、生命体征趋势和设备健康。",
        "按需检索本地 RAG 知识库，用于健康建议、设备说明和桌宠话术模板。",
        "按需调用实时工具查询天气、空气质量和配置后的网页搜索结果，并在未配置时说明边界。",
        "在设备数据可信度不足时触发 DeviceGuardian handoff，并降低相关结论强度。",
        "输出结构化 HealthAgentFinalOutput，包括摘要、风险标签、建议、桌宠动作、置信度和 trace。",
        "回答功能介绍、使用方式、日期时间和一般说明类问题，并结合 AIContext 给出安全、简洁的回复。",
    ],
    "boundaries": [
        "不输出医疗诊断、疾病判断、治疗建议或必须就医等表达。",
        "不编造并非来自 AIContext、工具 observation 或 RAG 的当前状态数据。",
        "工具不能覆盖的问题，可以基于已有上下文和能力清单直接说明边界或追问。",
    ],
    "capability_answer_style": (
        "功能介绍要直接面向用户，用第一人称说明：我可以读取当前办公健康状态、分析久坐/饮水/环境/设备可信度、"
        "检索本地健康知识、查询天气/空气质量、生成桌宠提醒动作和保留 trace；同时说明我不做医疗诊断或治疗建议。"
    ),
}


class LangGraphDeepSeekReactGraph:
    """真实 DeepSeek tool-calling ReAct 图。

    Python 只负责 LangGraph 状态迁移、工具执行、guardrails、停止条件和 trace。
    业务工具选择由 DeepSeek 基于 instructions、tool specs、AIContext 与 observation 决定。
    """

    graph_name = "healthdesk_langgraph_deepseek_react_graph"

    def __init__(
        self,
        *,
        repo: HealthRepository,
        registry: AgentToolRegistry,
        settings: AgentRuntimeSettings,
        chat_model: Any,
    ) -> None:
        self.repo = repo
        self.registry = registry
        self.settings = settings
        self.reason_node = DeepSeekReasonNode(registry=registry, settings=settings, chat_model=chat_model)
        self._compiled = self._compile()

    def invoke(self, state: AgentState) -> AgentState:
        state["_started_at_ms"] = now_ms()
        return self._compiled.invoke(state)

    def _compile(self) -> Any:
        from langgraph.graph import END, START, StateGraph

        graph = StateGraph(AgentState)
        graph.add_node("load_context_node", lambda state: load_context_node(state, repo=self.repo))
        graph.add_node("agent_reason_node", self.reason_node)
        graph.add_node("tool_execute_node", lambda state: _execute_with_tool_guard(state, registry=self.registry))
        graph.add_node("observe_node", _observe_with_tool_message)
        graph.add_node("finalize_node", finalize_node)
        graph.add_node("guardrails_node", guardrails_node)
        graph.add_node("save_trace_node", lambda state: _save_real_trace(state, repo=self.repo, graph_name=self.graph_name))

        graph.add_edge(START, "load_context_node")
        graph.add_conditional_edges(
            "load_context_node",
            _route_after_load_context,
            {"agent_reason_node": "agent_reason_node", "finalize_node": "finalize_node"},
        )
        graph.add_conditional_edges(
            "agent_reason_node",
            _route_after_reason,
            {"tool_execute_node": "tool_execute_node", "finalize_node": "finalize_node"},
        )
        graph.add_edge("tool_execute_node", "observe_node")
        graph.add_conditional_edges(
            "observe_node",
            lambda state: _route_after_observe(state, self.settings),
            {"agent_reason_node": "agent_reason_node", "finalize_node": "finalize_node"},
        )
        graph.add_edge("finalize_node", "guardrails_node")
        graph.add_edge("guardrails_node", "save_trace_node")
        graph.add_edge("save_trace_node", END)
        return graph.compile()


class DeepSeekReasonNode:
    """调用 DeepSeek，让模型选择下一步 tool call 或提交结构化最终输出。"""

    def __init__(self, *, registry: AgentToolRegistry, settings: AgentRuntimeSettings, chat_model: Any) -> None:
        self.registry = registry
        self.settings = settings
        self.tool_names = set(registry.names())
        tools = [*registry.to_langchain_tools(), _build_final_output_tool()]
        try:
            self.bound_model = chat_model.bind_tools(tools, parallel_tool_calls=False)
        except TypeError:
            self.bound_model = chat_model.bind_tools(tools)

    def __call__(self, state: AgentState) -> AgentState:
        if state.get("step_count", 0) >= self.settings.max_agent_steps:
            state["stop_reason"] = "max_steps"
            return append_trace_step(
                state,
                node_name="agent_reason_node",
                action_type="stop_decision",
                observation_summary="已达到 max_steps，进入最终输出阶段。",
                stop_reason="max_steps",
            )

        messages = _ensure_messages(state, self.registry, self.settings)
        state["step_count"] = state.get("step_count", 0) + 1
        try:
            response = self.bound_model.invoke(messages)
        except Exception as exc:
            state.setdefault("errors", []).append(f"DeepSeek 调用失败: {exc}")
            return append_trace_step(
                state,
                node_name="agent_reason_node",
                action_type="model_error",
                observation_summary="DeepSeek 调用失败，进入 fallback finalizer。",
                stop_reason="tool_error_stop",
            )

        tool_calls = _coerce_tool_calls(response)
        if len(tool_calls) > 1:
            status = dict(state.get("guardrail_status", {}))
            status["tool_guard"] = "multiple_tool_calls_trimmed_to_first"
            state["guardrail_status"] = status
        if tool_calls:
            selected_tool_call = tool_calls[0]
            state["messages"] = [*messages, _single_tool_call_message(response, selected_tool_call)]
            return self._handle_tool_call(state, selected_tool_call)

        state["messages"] = [*messages, response]
        final_args = _extract_json_object(getattr(response, "content", ""))
        if final_args is not None:
            return self._accept_final_output(state, final_args, source="content_json")

        plain_text = _extract_text_content(getattr(response, "content", ""))
        if plain_text:
            return self._accept_final_output(state, {"health_summary": plain_text, "confidence": 0.6}, source="content_text")

        state.setdefault("errors", []).append("DeepSeek 未返回 tool_call，也未返回可校验的最终 JSON。")
        return append_trace_step(
            state,
            node_name="agent_reason_node",
            action_type="model_error",
            observation_summary="模型没有提交工具调用或结构化最终输出。",
            stop_reason="tool_error_stop",
        )

    def _handle_tool_call(self, state: AgentState, tool_call: dict[str, Any]) -> AgentState:
        tool_name = str(tool_call.get("name", ""))
        tool_args = dict(tool_call.get("args") or {})
        tool_call_id = str(tool_call.get("id") or f"tool-{state.get('step_count', 0)}")
        if tool_name == FINAL_OUTPUT_TOOL_NAME:
            return self._accept_final_output(state, tool_args, source=FINAL_OUTPUT_TOOL_NAME)

        status = dict(state.get("guardrail_status", {}))
        if tool_name not in self.tool_names:
            status["tool_guard"] = "unknown_tool_blocked"
            state["guardrail_status"] = status
            state.setdefault("errors", []).append(f"DeepSeek 请求了未注册工具: {tool_name}")
            return append_trace_step(
                state,
                node_name="agent_reason_node",
                action_type="tool_guardrail_fail",
                tool_name=tool_name,
                tool_args=tool_args,
                observation_summary="模型请求的工具未注册，已阻断。",
                stop_reason="tool_error_stop",
            )

        status["tool_guard"] = True
        state["guardrail_status"] = status
        state["pending_tool_call"] = {
            "tool_name": tool_name,
            "tool_args": tool_args,
            "tool_call_id": tool_call_id,
            "reasoning_summary": f"DeepSeek 选择调用工具 {tool_name}。",
        }
        state.setdefault("model_calls", []).append(
            {
                "runtime": "langgraph_deepseek",
                "reasoning_summary": f"DeepSeek 选择调用工具 {tool_name}。",
                "selected_tool": tool_name,
                "tool_call_id": tool_call_id,
            }
        )
        return append_trace_step(
            state,
            node_name="agent_reason_node",
            action_type="tool_call_decision",
            tool_name=tool_name,
            tool_args=tool_args,
            observation_summary=f"DeepSeek 选择调用工具 {tool_name}。",
        )

    def _accept_final_output(self, state: AgentState, final_args: dict[str, Any], *, source: str) -> AgentState:
        payload = _normalize_final_output_args(final_args, state)
        try:
            output = HealthAgentFinalOutput.model_validate(payload)
        except ValidationError as exc:
            state.setdefault("errors", []).append(f"DeepSeek final output schema 校验失败: {exc}")
            return append_trace_step(
                state,
                node_name="agent_reason_node",
                action_type="schema_validation_error",
                observation_summary="模型提交的最终输出未通过 HealthAgentFinalOutput 校验。",
                stop_reason="tool_error_stop",
            )

        state["final_output"] = output.model_dump()
        state["stop_reason"] = output.stop_reason
        state.setdefault("model_calls", []).append(
            {
                "runtime": "langgraph_deepseek",
                "reasoning_summary": "DeepSeek 提交结构化最终输出。",
                "selected_tool": FINAL_OUTPUT_TOOL_NAME if source == FINAL_OUTPUT_TOOL_NAME else None,
            }
        )
        return append_trace_step(
            state,
            node_name="agent_reason_node",
            action_type="final_decision",
            tool_name=FINAL_OUTPUT_TOOL_NAME if source == FINAL_OUTPUT_TOOL_NAME else None,
            observation_summary="DeepSeek 提交的最终输出已通过 HealthAgentFinalOutput 校验。",
            stop_reason=output.stop_reason,
        )


def _execute_with_tool_guard(state: AgentState, *, registry: AgentToolRegistry) -> AgentState:
    pending = state.get("pending_tool_call")
    status = dict(state.get("guardrail_status", {}))
    if pending and pending.get("tool_name") not in registry.names():
        status["tool_guard"] = "unknown_tool_blocked"
        state["guardrail_status"] = status
        state.setdefault("errors", []).append(f"未注册工具: {pending.get('tool_name')}")
        return state
    status["tool_guard"] = status.get("tool_guard", True)
    state["guardrail_status"] = status
    return tool_execute_node(state, registry=registry)


def _observe_with_tool_message(state: AgentState) -> AgentState:
    pending = state.get("pending_tool_call")
    state = observe_node(state)
    observation = state.get("last_observation")
    if pending and observation and pending.get("tool_call_id"):
        from langchain_core.messages import ToolMessage

        content = _json_dumps(
            {
                "success": observation.get("success", True),
                "tool_name": observation.get("tool_name"),
                "summary": observation.get("summary", ""),
                "raw_data": observation.get("raw_data", {}),
                "metadata": observation.get("metadata", {}),
            }
        )
        state["messages"] = [
            *state.get("messages", []),
            ToolMessage(content=content, tool_call_id=str(pending["tool_call_id"])),
        ]
    status = dict(state.get("guardrail_status", {}))
    status["observation_guard"] = not bool(state.get("errors"))
    state["guardrail_status"] = status
    return state


def _route_after_load_context(state: AgentState) -> str:
    return "finalize_node" if state.get("errors") else "agent_reason_node"


def _route_after_reason(state: AgentState) -> str:
    if state.get("pending_tool_call"):
        return "tool_execute_node"
    return "finalize_node"


def _route_after_observe(state: AgentState, settings: AgentRuntimeSettings) -> str:
    if state.get("final_output"):
        state["stop_reason"] = state.get("stop_reason") or "final_schema_valid_stop"
        return "finalize_node"
    if state.get("errors"):
        state["stop_reason"] = state.get("stop_reason") or "tool_error_stop"
        return "finalize_node"
    if state.get("guardrail_status", {}).get("failed"):
        state["stop_reason"] = state.get("stop_reason") or "guardrail_fail_stop"
        return "finalize_node"
    if same_tool_limit_hit(state, settings):
        state["stop_reason"] = "max_same_tool_calls"
        return "finalize_node"
    if no_new_information_hit(state):
        state["stop_reason"] = "no_new_information_stop"
        return "finalize_node"
    if state.get("step_count", 0) >= settings.max_agent_steps:
        state["stop_reason"] = "max_steps"
        return "finalize_node"
    return "agent_reason_node"


def _save_real_trace(state: AgentState, *, repo: HealthRepository, graph_name: str) -> AgentState:
    ended_at = now_ms()
    steps = state.get("trace_steps", [])
    first_step_ms = steps[0].get("created_at_ms") if steps else None
    started_at = int(state.get("_started_at_ms") or first_step_ms or ended_at)
    trace_payload = build_trace_payload(state, graph_name=graph_name, started_at=started_at, ended_at=ended_at)
    trace_payload["runtime_kind"] = "langgraph_deepseek"
    return save_trace_node(state, repo=repo, trace_payload=trace_payload)


def _ensure_messages(state: AgentState, registry: AgentToolRegistry, settings: AgentRuntimeSettings) -> list[Any]:
    messages = list(state.get("messages") or [])
    if messages:
        return messages

    from langchain_core.messages import HumanMessage, SystemMessage

    tool_names = [*registry.names(), FINAL_OUTPUT_TOOL_NAME]
    system_text = (
        "你是 HealthCoordinatorAgent，一个办公健康真实 Agent。"
        "你必须基于 Goal、AIContext、工具说明和 observation 自主选择下一步 action。"
        "不要使用 Python 规则假装 planner；真实业务工具选择只能通过你的 tool_calls 表达。"
        "每一轮最多调用一个工具。"
        "如果用户询问你是谁、你会哪些功能、如何使用、当前日期时间或一般说明，"
        "且不需要新增健康知识检索或实时状态计算，直接调用 submit_final_output，"
        "根据 agent_capabilities、current_datetime_local 和 AIContext 回答；不要为了这类问题调用 search_* 工具。"
        "当当前工具列表无法直接解决用户提问，但你可以基于 AIContext、agent_capabilities 和已有上下文安全回答时，"
        "用 LLM 综合后直接调用 submit_final_output；如果缺少必要事实，简短说明边界或提出澄清问题。"
        "如果用户要求分析当前办公健康状态、生成桌宠提醒、现在状态怎么样、做一次综合办公健康检查，"
        "且 AIContext.office_health_snapshot 已存在，直接基于该快照调用 submit_final_output；不要调用任何工具。"
        "只有当 AIContext.office_health_snapshot 缺失或明显不完整时，才调用 analyze_office_health_snapshot 一次获取完整 observation；"
        "不要拆成 get_current_state、get_sensor_health 和多个 analyze_* 工具的串行调用。"
        "analyze_office_health_snapshot 的 observation 已包含 recommendations 和 pet_action 时，下一步直接调用 submit_final_output；"
        "不要再调用 create_pet_action。"
        "当前网页版交互只需要把 final_output 返回给前端；不要调用 save_pet_action、save_daily_report 或 update_user_memory，"
        "除非用户明确要求保存、记录、生成并保存日报或更新记忆。"
        "对于这类直接回答，HealthAgentFinalOutput.health_summary 必须是给用户看的最终答复，"
        "不要写成“用户询问...”或“基于能力清单...”这类内部任务摘要。"
        "功能介绍必须用第一人称列出关键能力和边界；日期时间问题必须直接给出具体日期或时间。"
        "面向用户的 health_summary 使用简洁纯文本，可用编号，不要使用 Markdown 强调符号、表格或 emoji。"
        "网页版桌宠交互必须短输出：health_summary 控制在 220 个中文字符以内，recommendations 最多 3 条，"
        "pet_action.message 控制在 40 个中文字符以内。"
        "用户当前状态只能来自 AIContext、get_current_state、SQLite 状态工具或 sensor_health 工具。"
        "RAG 只提供健康建议、设备说明和话术模板，不能替代当前状态。"
        "天气、室外温湿度、降雨、风力、PM2.5、AQI、紫外线等外部实时环境信息必须调用 get_weather；"
        "其他需要联网核验的实时网页信息才调用 search_web。未拿到工具结果时，不要编造实时事实。"
        "如设备置信度低或 sensor_health 异常，可触发 handoff_to_device_guardian。"
        "当信息足够时，调用 submit_final_output 提交 HealthAgentFinalOutput；不要输出散文作为最终答案。"
        "不要输出医疗诊断、疾病判断或必须就医等表达。"
    )
    human_payload = {
        "task": state["task"],
        "user_id": state["user_id"],
        "trace_id": state["trace_id"],
        "runtime": "langgraph_deepseek",
        "available_tools": tool_names,
        "current_datetime_local": datetime.now().astimezone().isoformat(timespec="seconds"),
        "interaction_policy": {
            "surface": "web_pet",
            "return_final_output_to_frontend": True,
            "persist_pet_action_by_default": False,
            "persist_memory_by_default": False,
            "max_health_summary_chars": 220,
            "max_recommendations": 3,
            "max_pet_message_chars": 40,
        },
        "agent_capabilities": AGENT_CAPABILITIES,
        "stop_conditions": {
            "max_steps": settings.max_agent_steps,
            "max_same_tool_calls": settings.max_same_tool_calls,
            "no_new_information_stop": True,
            "tool_error_stop": True,
            "guardrail_fail_stop": True,
            "final_schema_valid_stop": True,
        },
        "ai_context": state.get("ai_context") or {},
    }
    messages = [SystemMessage(content=system_text), HumanMessage(content=_json_dumps(human_payload))]
    state["messages"] = messages
    return messages


def _build_final_output_tool() -> Any:
    from langchain_core.tools import StructuredTool

    def submit_final_output(**_: Any) -> str:
        return "final output submitted"

    return StructuredTool.from_function(
        func=submit_final_output,
        name=FINAL_OUTPUT_TOOL_NAME,
        description=(
            "当 observation 已足够回答用户目标，或用户问题可由 LLM 基于 AIContext、agent_capabilities 和已有上下文直接回答时调用。"
            "能力介绍、日期时间、使用方式、普通说明和工具无法覆盖但可安全回答的问题，都可以通过本工具提交最终答案。"
            "health_summary 必须是面向用户的最终答复，不要填内部任务摘要。"
            "参数必须符合 HealthAgentFinalOutput。"
            "runtime 必须是 langgraph_deepseek，trace_id 必须使用当前 trace_id。"
        ),
        args_schema=HealthAgentFinalOutput,
    )


def _normalize_final_output_args(final_args: dict[str, Any], state: AgentState) -> dict[str, Any]:
    payload = dict(final_args)
    payload["runtime"] = "langgraph_deepseek"
    payload["trace_id"] = state["trace_id"]
    payload.setdefault("task_type", "office_health_check")
    state_risk_tags = list(state.get("risk_tags", []))
    if state_risk_tags:
        payload["risk_tags"] = sorted(set([*(payload.get("risk_tags") or []), *state_risk_tags]))
    else:
        payload.setdefault("risk_tags", [])
    payload.setdefault("recommendations", [])
    payload.setdefault("confidence", 0.7)
    if not payload.get("data_sources_used"):
        payload["data_sources_used"] = _data_sources_used(state)
    if not payload.get("tools_called"):
        payload["tools_called"] = [call.get("tool_name", "") for call in state.get("tool_calls", [])]
    payload["guardrail_status"] = {**state.get("guardrail_status", {}), **dict(payload.get("guardrail_status") or {})}
    payload["stop_reason"] = "final_schema_valid_stop"
    return payload


def _coerce_tool_calls(response: Any) -> list[dict[str, Any]]:
    calls = [_normalize_tool_call(call) for call in list(getattr(response, "tool_calls", []) or [])]
    calls = [call for call in calls if call is not None]
    if calls:
        return calls

    additional_kwargs = dict(getattr(response, "additional_kwargs", {}) or {})
    raw_calls = additional_kwargs.get("tool_calls") or additional_kwargs.get("tool_call") or []
    if isinstance(raw_calls, dict):
        raw_calls = [raw_calls]
    if not isinstance(raw_calls, list):
        return []
    return [call for call in (_normalize_tool_call(raw) for raw in raw_calls) if call is not None]


def _normalize_tool_call(call: Any) -> dict[str, Any] | None:
    if not isinstance(call, dict):
        return None

    if "function" in call and isinstance(call["function"], dict):
        function = call["function"]
        name = function.get("name")
        args = _parse_tool_args(function.get("arguments"))
    else:
        name = call.get("name")
        args = _parse_tool_args(call.get("args") if "args" in call else call.get("arguments"))

    if not name:
        return None
    return {
        "name": str(name),
        "args": args,
        "id": str(call.get("id") or call.get("tool_call_id") or f"tool-{name}"),
    }


def _parse_tool_args(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _single_tool_call_message(response: Any, tool_call: dict[str, Any]) -> Any:
    """Return an AIMessage whose tool_calls match the single tool we execute."""

    from langchain_core.messages import AIMessage

    additional_kwargs = dict(getattr(response, "additional_kwargs", {}) or {})
    additional_kwargs.pop("tool_calls", None)
    return AIMessage(
        content=getattr(response, "content", "") or "",
        additional_kwargs=additional_kwargs,
        tool_calls=[tool_call],
        response_metadata=getattr(response, "response_metadata", {}) or {},
    )


def _extract_json_object(content: Any) -> dict[str, Any] | None:
    if isinstance(content, dict):
        return content
    text = _extract_text_content(content)
    if not text:
        return None
    for candidate in _json_candidates(text):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _extract_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(part.strip() for part in parts if part and part.strip()).strip()
    return ""


def _json_candidates(text: str) -> list[str]:
    stripped = text.strip()
    candidates = [stripped]
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].lstrip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        fenced = "\n".join(lines).strip()
        if fenced:
            candidates.append(fenced)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end > start:
        candidates.append(stripped[start : end + 1])
    return list(dict.fromkeys(candidates))


def _data_sources_used(state: AgentState) -> list[str]:
    sources = {"ai_context"}
    for call in state.get("tool_calls", []):
        name = call.get("tool_name")
        if name:
            sources.add(str(name))
    if state.get("retrieved_chunks"):
        sources.add("rag")
    if state.get("device_guardian_result"):
        sources.add("device_guardian_handoff")
    return sorted(sources)


def _json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=_json_default)


def _json_default(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump()
    return str(value)
