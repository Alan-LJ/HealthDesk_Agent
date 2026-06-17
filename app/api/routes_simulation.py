from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.main_state import repo, simulator

router = APIRouter(prefix="/simulation", tags=["simulation"])


@router.post("/scenario/{scenario_name}")
def switch_scenario(scenario_name: str) -> dict:
    """切换模拟场景。"""

    try:
        simulator.set_scenario(scenario_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"scenario": scenario_name}


@router.post("/tick")
def tick() -> dict:
    """生成一条模拟状态并写入 SQLite。"""

    result = simulator.tick(repo.get_environment_settings())
    repo.save_tick(result.raw, result.feature, result.state, result.events, result.sensor_health)
    return {
        "scenario": result.scenario_name,
        "state": result.state.model_dump(),
        "events": [event.model_dump() for event in result.events],
        "sensor_health": [item.model_dump() for item in result.sensor_health],
    }
