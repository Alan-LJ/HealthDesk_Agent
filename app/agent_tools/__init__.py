"""LangGraph/LangChain Agent 工具绑定层。

工具绑定层负责把内部 handler 包装成模型可见的工具。当前支持本地
LocalToolBinding；如果安装了 langchain_core，后续可转换为 StructuredTool。
"""

from app.agent_tools.tool_registry import AgentToolRegistry, build_agent_tools
from app.agent_tools.tool_schemas import ToolObservation

__all__ = ["AgentToolRegistry", "ToolObservation", "build_agent_tools"]
