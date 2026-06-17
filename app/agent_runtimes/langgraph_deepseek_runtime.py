from __future__ import annotations

from threading import Lock
from typing import Any

from app.agent_runtimes.base import AgentRunRequest, AgentRunResult, BaseAgentRuntime
from app.agent_runtimes.settings import AgentRuntimeSettings, load_runtime_settings
from app.agent_tools.tool_registry import build_agent_tools
from app.graph.builder import create_graph_state
from app.graph.langgraph_deepseek_graph import LangGraphDeepSeekReactGraph
from app.storage.repository import HealthRepository


class LangGraphDeepSeekRuntime(BaseAgentRuntime):
    """真实 LangGraph + DeepSeek runtime。

    该 runtime 使用 DeepSeek tool calling 作为 real Agent 的 planner：
    Python 不根据业务规则决定该调用哪个健康工具，只执行模型返回的 tool_call、
    写入 observation、检查停止条件和保存 trace。
    """

    runtime_name = "langgraph_deepseek"

    def __init__(
        self,
        repo: HealthRepository | None = None,
        settings: AgentRuntimeSettings | None = None,
        chat_model: Any | None = None,
    ) -> None:
        self.settings = settings or load_runtime_settings()
        self.repo = repo or HealthRepository(self.settings.database_path)
        self.chat_model = chat_model
        self._graph: LangGraphDeepSeekReactGraph | None = None
        self._registry = None
        self._chat_model_instance: Any | None = chat_model
        self._cache_lock = Lock()

    def run(self, request: AgentRunRequest) -> AgentRunResult:
        """运行一次真实 DeepSeek ReAct Agent。"""

        if not self.settings.has_deepseek_key and self.chat_model is None:
            raise RuntimeError("DEEPSEEK_API_KEY 未配置，无法运行 langgraph_deepseek runtime。")
        self._check_optional_dependencies()

        graph = self._get_graph()
        state = create_graph_state(task=request.task, user_id=request.user_id, runtime="langgraph_deepseek")
        state = graph.invoke(state)
        final_output = state.get("final_output") or {}
        return AgentRunResult(
            runtime=self.runtime_name,
            trace_id=state["trace_id"],
            message="已运行 LangGraph + DeepSeek real Agent；工具选择来自模型 tool_calls，不是 Python 规则 planner。",
            stop_reason=state.get("stop_reason"),
            final_output=final_output,
            warnings=[] if final_output else ["真实 Agent 未得到可校验 final output，已进入安全 fallback。"],
            metadata={
                "runtime_kind": "langgraph_deepseek",
                "graph_name": graph.graph_name,
                "model_backend": "injected_test_model" if self.chat_model is not None else "ChatDeepSeek",
                "tools_called": [call.get("tool_name") for call in state.get("tool_calls", [])],
                "handoffs_called": [
                    call.get("tool_name")
                    for call in state.get("tool_calls", [])
                    if str(call.get("tool_name", "")).startswith("handoff_")
                ],
                "observation_count": len(state.get("observations", [])),
                "model_call_count": len(state.get("model_calls", [])),
                "rag_chunk_count": len(state.get("retrieved_chunks", [])),
                "step_count": len(state.get("trace_steps", [])),
                "guardrail_status": state.get("guardrail_status", {}),
            },
        )

    def _get_graph(self) -> LangGraphDeepSeekReactGraph:
        """Lazily build and reuse model/tool bindings and compiled LangGraph."""

        if self._graph is not None:
            return self._graph
        with self._cache_lock:
            if self._graph is None:
                registry = build_agent_tools(self.repo, settings=self.settings)
                chat_model = self._chat_model_instance or self._build_chat_model()
                self._registry = registry
                self._chat_model_instance = chat_model
                self._graph = LangGraphDeepSeekReactGraph(
                    repo=self.repo,
                    registry=registry,
                    settings=self.settings,
                    chat_model=chat_model,
                )
        return self._graph

    def _build_chat_model(self) -> Any:
        from langchain_deepseek import ChatDeepSeek

        model_kwargs: dict[str, Any] = {
            "model": self.settings.deepseek_model,
            "api_key": self.settings.deepseek_api_key,
            "base_url": self.settings.deepseek_base_url,
            "timeout": 30,
            "max_retries": 1,
        }
        if self.settings.deepseek_thinking == "enabled":
            model_kwargs["reasoning_effort"] = self.settings.deepseek_reasoning_effort
            model_kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
        else:
            model_kwargs["temperature"] = 0.2
            model_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
        return ChatDeepSeek(**model_kwargs)

    @staticmethod
    def _check_optional_dependencies() -> None:
        """检查 LangGraph/DeepSeek 依赖是否可导入。"""

        missing: list[str] = []
        for module_name in ["langgraph", "langchain_core", "langchain_deepseek"]:
            try:
                __import__(module_name)
            except ImportError:
                missing.append(module_name)
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(f"缺少 LangGraph + DeepSeek 依赖: {joined}。请先安装 requirements.txt 中的相关包。")
