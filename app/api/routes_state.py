from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.main_state import repo

router = APIRouter(tags=["state"])


@router.get("/state/current")
def current_state() -> dict:
    state = repo.get_current_state()
    if state is None:
        raise HTTPException(status_code=404, detail="请先调用 /simulation/tick")
    return state.model_dump()


@router.get("/events/recent")
def recent_events(limit: int = 10) -> list[dict]:
    return [event.model_dump() for event in repo.get_recent_events(limit)]
