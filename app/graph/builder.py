from __future__ import annotations

from app.graph.state import AgentState, create_initial_agent_state


def create_graph_state(task: str, user_id: str = "default", runtime: str = "langgraph_deepseek") -> AgentState:
    """创建 LangGraph + DeepSeek 真实 Agent 图输入状态。"""

    return create_initial_agent_state(task=task, user_id=user_id, runtime="langgraph_deepseek")
