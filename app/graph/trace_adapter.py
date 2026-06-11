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

    steps = list(state.get("trace_steps", []))
    steps.append(
        {
            "step_index": len(steps) + 1,
            "node_name": node_name,
            "action_type": action_type,
            "tool_name": tool_name,
            "tool_args": tool_args or {},
            "observation_summary": observation_summary,
            "stop_reason": stop_reason,
            "created_at_ms": now_ms(),
        }
    )
    state["trace_steps"] = steps
    return state


def build_trace_payload(state: AgentState, *, graph_name: str, started_at: int, ended_at: int) -> dict[str, Any]:
    """把 AgentState 转成 SQLite 可保存的 trace JSON。"""

    observations = state.get("observations", [])
    model_calls = state.get("model_calls", [])
    tool_calls = state.get("tool_calls", [])
    return {
        "trace_id": state["trace_id"],
        "runtime": state["runtime"],
        "runtime_kind": state["runtime"],
        "graph_name": graph_name,
        "user_task": state["task"],
        "input_context": state.get("ai_context") or {},
        "steps": state.get("trace_steps", []),
        "model_calls": model_calls,
        "model_call_count": len(model_calls),
        "tool_calls": tool_calls,
        "tools_called": [call.get("tool_name", "") for call in tool_calls],
        "observations": observations,
        "rag_chunks": state.get("retrieved_chunks", []),
        "guardrail_checks": state.get("guardrail_status", {}),
        "final_output": state.get("final_output") or {},
        "errors": state.get("errors", []),
        "started_at": started_at,
        "ended_at": ended_at,
        "latency_ms": ended_at - started_at,
    }
