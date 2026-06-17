from __future__ import annotations

from typing import Any

from app.graph.state import AgentState
from app.schemas.common import now_ms


def append_trace_step(
    state: AgentState,
    *,
    node_name: str,
    action_type: str,
    tool_name: str | None = None,
    tool_args: dict[str, Any] | None = None,
    observation_summary: str = "",
    stop_reason: str | None = None,
) -> AgentState:
    """向 AgentState 追加一条可展示 trace step。

    这里刻意只记录 action 摘要、工具名、参数和 observation summary，不记录完整
    chain-of-thought，方便面试展示同时避免暴露模型内部推理。
    """

    steps = _as_list(state.get("trace_steps", []))
    steps.append(
        {
            "step_index": len(steps) + 1,
            "node_name": node_name,
            "action_type": action_type,
            "tool_name": tool_name,
            "tool_args": tool_args if isinstance(tool_args, dict) else {},
            "observation_summary": str(observation_summary or ""),
            "stop_reason": stop_reason,
            "created_at_ms": now_ms(),
        }
    )
    state["trace_steps"] = steps
    return state


def build_trace_payload(state: AgentState, *, graph_name: str, started_at: int, ended_at: int) -> dict[str, Any]:
    """把 AgentState 转成 SQLite 可保存的 trace JSON。"""

    observations = _as_list(state.get("observations", []))
    model_calls = _as_list(state.get("model_calls", []))
    tool_calls = _normalize_tool_calls(state.get("tool_calls", []))
    runtime = str(state.get("runtime") or "langgraph_deepseek")
    return {
        "trace_id": str(state.get("trace_id") or ""),
        "runtime": runtime,
        "runtime_kind": runtime,
        "graph_name": graph_name,
        "user_task": str(state.get("task") or ""),
        "input_context": state.get("ai_context") if isinstance(state.get("ai_context"), dict) else {},
        "steps": _as_list(state.get("trace_steps", [])),
        "model_calls": model_calls,
        "model_call_count": len(model_calls),
        "tool_calls": tool_calls,
        "tools_called": [_tool_name(call) for call in tool_calls if _tool_name(call)],
        "observations": observations,
        "rag_chunks": _as_list(state.get("retrieved_chunks", [])),
        "guardrail_checks": state.get("guardrail_status") if isinstance(state.get("guardrail_status"), dict) else {},
        "final_output": state.get("final_output") if isinstance(state.get("final_output"), dict) else {},
        "errors": [str(item) for item in _as_list(state.get("errors", []))],
        "started_at": started_at,
        "ended_at": ended_at,
        "latency_ms": ended_at - started_at,
    }


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _normalize_tool_calls(value: Any) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for item in _as_list(value):
        if isinstance(item, dict):
            calls.append(item)
        else:
            calls.append({"tool_name": "", "raw": str(item)})
    return calls


def _tool_name(call: dict[str, Any]) -> str:
    return str(call.get("tool_name") or call.get("name") or "")
