from __future__ import annotations

import uuid
from typing import Any, Literal, TypedDict


RuntimeKind = Literal["langgraph_deepseek"]


class AgentState(TypedDict, total=False):
    """LangGraph 在节点之间传递的 Agent 状态。

    AgentState 可以理解为一次 Agent run 的“工作台”。每个节点都从这里读取
    已有信息，并把自己的结果写回这里。它不是数据库表，也不是最终输出，
    而是 ReAct 循环中承载 task、tool calls、observations 和 stop_reason 的状态容器。

    注意：这里不保存完整 chain-of-thought，只保存适合展示和调试的摘要字段。
    """

    task: str
    user_id: str
    runtime: RuntimeKind
    ai_context: dict[str, Any] | None
    messages: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    observations: list[dict[str, Any]]
    retrieved_chunks: list[dict[str, Any]]
    risk_tags: list[str]
    health_analysis: dict[str, Any] | None
    device_guardian_result: dict[str, Any] | None
    pet_action: dict[str, Any] | None
    pending_tool_call: dict[str, Any] | None
    last_observation: dict[str, Any] | None
    final_output: dict[str, Any] | None
    guardrail_status: dict[str, Any]
    trace_steps: list[dict[str, Any]]
    model_calls: list[dict[str, Any]]
    trace_id: str
    _started_at_ms: int
    step_count: int
    stop_reason: str | None
    errors: list[str]


def create_initial_agent_state(task: str, user_id: str = "default", runtime: RuntimeKind = "langgraph_deepseek") -> AgentState:
    """创建一份 LangGraph 初始状态。

    后续 runtime 进入图之前会调用这个函数，确保列表和字典字段都有独立默认值，
    避免多个 Agent run 之间共享可变对象。
    """

    return AgentState(
        task=task,
        user_id=user_id,
        runtime=runtime,
        ai_context=None,
        messages=[],
        tool_calls=[],
        observations=[],
        retrieved_chunks=[],
        risk_tags=[],
        health_analysis=None,
        device_guardian_result=None,
        pet_action=None,
        pending_tool_call=None,
        last_observation=None,
        final_output=None,
        guardrail_status={},
        trace_steps=[],
        model_calls=[],
        trace_id=str(uuid.uuid4()),
        _started_at_ms=0,
        step_count=0,
        stop_reason=None,
        errors=[],
    )
