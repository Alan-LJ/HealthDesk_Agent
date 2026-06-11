from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException

from app.main_state import repo
from app.storage.db import connect

router = APIRouter(tags=["traces"])


def _load_trace_rows(limit: int = 20) -> list[dict[str, Any]]:
    """读取最近的 Agent trace。

    SQLite 日志表统一存 JSON，这里只做 API 层展示，不改变数据库结构。
    """

    with connect(repo.db_path) as conn:
        rows = conn.execute(
            "SELECT id, created_at_ms, payload_json FROM agent_trace_log ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    traces: list[dict[str, Any]] = []
    for row in rows:
        payload = json.loads(row["payload_json"])
        payload = _normalize_trace_payload(payload)
        payload.setdefault("id", row["id"])
        payload.setdefault("created_at_ms", row["created_at_ms"])
        traces.append(payload)
    return traces


def _normalize_trace_payload(payload: dict[str, Any]) -> dict[str, Any]:
    final_output = payload.get("final_output") if isinstance(payload.get("final_output"), dict) else {}
    runtime = payload.get("runtime_kind") or payload.get("runtime") or final_output.get("runtime")
    tool_calls = payload.get("tool_calls") or []
    model_calls = payload.get("model_calls") or []
    payload.setdefault("runtime_kind", runtime or "unknown")
    payload.setdefault("model_call_count", len(model_calls))
    payload.setdefault("tools_called", [call.get("tool_name", "") for call in tool_calls if isinstance(call, dict)])
    return payload


@router.get("/traces/recent")
def recent_traces(limit: int = 20) -> list[dict[str, Any]]:
    """返回最近 Agent trace。"""

    safe_limit = max(1, min(limit, 100))
    return _load_trace_rows(safe_limit)


@router.get("/traces/{trace_id}")
def trace_detail(trace_id: str) -> dict[str, Any]:
    """按 trace_id 查询单次 Agent 运行 trace。"""

    with connect(repo.db_path) as conn:
        rows = conn.execute("SELECT id, created_at_ms, payload_json FROM agent_trace_log ORDER BY id DESC").fetchall()
    for row in rows:
        payload = json.loads(row["payload_json"])
        payload = _normalize_trace_payload(payload)
        if payload.get("trace_id") == trace_id:
            payload.setdefault("id", row["id"])
            payload.setdefault("created_at_ms", row["created_at_ms"])
            return payload
    raise HTTPException(status_code=404, detail=f"trace not found: {trace_id}")
