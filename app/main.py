from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import (
    routes_agent_runtime,
    routes_pet,
    routes_simulation,
    routes_state,
    routes_traces,
)

app = FastAPI(title="HealthDesk Agent", version="0.1.0")
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/health")
def health() -> dict:
    """服务健康检查。"""

    return {"status": "ok", "service": "healthdesk-agent"}


app.include_router(routes_simulation.router)
app.include_router(routes_state.router)
app.include_router(routes_agent_runtime.router)
app.include_router(routes_traces.router)
app.include_router(routes_pet.router)
