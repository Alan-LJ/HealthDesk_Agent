from __future__ import annotations

from typing import Any

from app.agent_tools.action_tools import build_action_tools
from app.agent_tools.analysis_tools import build_analysis_tools
from app.agent_tools.context_tools import build_context_tools
from app.agent_tools.handoff_tools import build_handoff_tools
from app.agent_tools.local_tool import LocalToolBinding
from app.agent_tools.memory_tools import build_memory_tools
from app.agent_tools.rag_tools import build_rag_tools
from app.agent_tools.realtime_tools import build_realtime_tools
from app.storage.repository import HealthRepository


class AgentToolRegistry:
    """Agent 工具注册表。

    注册表只负责收集和查找工具，不负责决定真实 Agent 应调用哪个工具。
    在 LangGraph real runtime 中，工具选择由模型根据 tool specs 和 observation 决定。
    """

    def __init__(self, tools: list[LocalToolBinding[Any]]) -> None:
        self.tools = tools
        self._by_name = {tool.name: tool for tool in tools}

    def get(self, name: str) -> LocalToolBinding[Any]:
        if name not in self._by_name:
            raise KeyError(f"未注册 Agent tool: {name}")
        return self._by_name[name]

    def names(self) -> list[str]:
        return list(self._by_name)

    def descriptions(self) -> dict[str, str]:
        return {tool.name: tool.description for tool in self.tools}

    def to_langchain_tools(self) -> list:
        """转换为 LangChain StructuredTool 列表。"""

        return [tool.to_langchain_tool() for tool in self.tools]


def build_agent_tools(repo: HealthRepository, settings: Any | None = None) -> AgentToolRegistry:
    """构建完整 Agent 工具注册表。"""

    tools: list[LocalToolBinding[Any]] = []
    tools.extend(build_context_tools(repo))
    tools.extend(build_realtime_tools())
    tools.extend(build_rag_tools(settings=settings))
    tools.extend(build_analysis_tools(repo))
    tools.extend(build_handoff_tools(repo))
    tools.extend(build_action_tools(repo))
    tools.extend(build_memory_tools(repo))
    return AgentToolRegistry(tools)
