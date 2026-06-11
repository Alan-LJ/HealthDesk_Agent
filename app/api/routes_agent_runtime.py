from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.agent_runtimes import AgentRunRequest, LangGraphDeepSeekRuntime
from app.main_state import repo

router = APIRouter(tags=["agent-runtime"])
runtime = LangGraphDeepSeekRuntime(repo=repo)


@router.post("/agent/run")
def run_agent(request: AgentRunRequest) -> dict:
    """运行 LangGraph + DeepSeek 真实 Agent pipeline。"""

    try:
        result = runtime.run(request)
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return result.model_dump()
