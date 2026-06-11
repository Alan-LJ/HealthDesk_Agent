from __future__ import annotations

from collections import Counter

from app.agent_runtimes.settings import AgentRuntimeSettings
from app.graph.state import AgentState


def same_tool_limit_hit(state: AgentState, settings: AgentRuntimeSettings) -> bool:
    names = [call.get("tool_name") for call in state.get("tool_calls", [])]
    counts = Counter(names)
    return any(count > settings.max_same_tool_calls for count in counts.values())


def no_new_information_hit(state: AgentState) -> bool:
    """判断最近两次 observation 是否没有提供新信息。"""

    observations = state.get("observations", [])
    if len(observations) < 2:
        return False
    latest = observations[-1].get("summary")
    previous = observations[-2].get("summary")
    return bool(latest and latest == previous)
