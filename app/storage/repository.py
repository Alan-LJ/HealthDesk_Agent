from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.schemas.common import SensorHealth, TodaySummary, now_ms
from app.schemas.event import EventData, PetAction
from app.schemas.environment import EnvironmentThresholdSettings
from app.schemas.feature import FeatureData
from app.schemas.raw import RawData
from app.schemas.state import StateData
from app.storage.db import DEFAULT_DB_PATH, connect, init_db


ENVIRONMENT_SETTINGS_KEY_PREFIX = "environment_settings"


def _dump(obj: BaseModel | dict[str, Any]) -> str:
    """把 Pydantic 模型或字典转成 JSON 字符串，集中处理中文编码。"""

    if isinstance(obj, BaseModel):
        data = obj.model_dump()
    else:
        data = obj
    return json.dumps(data, ensure_ascii=False)


class HealthRepository:
    """
    SQLite Repository。

    Repository 把数据库细节包起来，让 Agent 和 API 像调用工具一样读写状态、事件和 trace。
    """

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = str(db_path)
        init_db(self.db_path)

    def append(self, table: str, payload: BaseModel | dict[str, Any]) -> None:
        """向日志表追加一条 JSON 记录。"""

        with connect(self.db_path) as conn:
            conn.execute(
                f"INSERT INTO {table} (created_at_ms, payload_json) VALUES (?, ?)",
                (now_ms(), _dump(payload)),
            )
            conn.commit()

    def save_tick(self, raw: list[RawData], feature: FeatureData, state: StateData, events: list[EventData], sensor_health: list[SensorHealth]) -> None:
        """保存一次模拟 tick 的完整结果。"""

        for item in raw:
            self.append("raw_log", item)
        self.append("feature_log", feature)
        self.append("state_log", state)
        for event in events:
            self.append("event_log", event)
        self.set_kv("sensor_health", [item.model_dump() for item in sensor_health])

    def latest_model(self, table: str, model: type[BaseModel]) -> BaseModel | None:
        """读取某个日志表最后一条记录并解析为 Pydantic 模型。"""

        with connect(self.db_path) as conn:
            row = conn.execute(f"SELECT payload_json FROM {table} ORDER BY id DESC LIMIT 1").fetchone()
        if not row:
            return None
        return model.model_validate(json.loads(row["payload_json"]))

    def list_models(self, table: str, model: type[BaseModel], limit: int = 10) -> list[BaseModel]:
        """读取最近 N 条记录，按时间从旧到新返回，便于 Agent 形成上下文。"""

        with connect(self.db_path) as conn:
            rows = conn.execute(f"SELECT payload_json FROM {table} ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [model.model_validate(json.loads(row["payload_json"])) for row in reversed(rows)]

    def get_current_state(self) -> StateData | None:
        return self.latest_model("state_log", StateData)  # type: ignore[return-value]

    def get_recent_events(self, limit: int = 10) -> list[EventData]:
        return self.list_models("event_log", EventData, limit)  # type: ignore[return-value]

    def get_sensor_health(self) -> list[SensorHealth]:
        data = self.get_kv("sensor_health", [])
        return [SensorHealth.model_validate(item) for item in data]

    def get_environment_settings(self, user_id: str = "default") -> EnvironmentThresholdSettings:
        data = self.get_kv(_environment_settings_key(user_id), None)
        if data is None:
            return EnvironmentThresholdSettings()
        return EnvironmentThresholdSettings.model_validate(data)

    def save_environment_settings(
        self,
        settings: EnvironmentThresholdSettings,
        user_id: str = "default",
    ) -> EnvironmentThresholdSettings:
        saved = settings.model_copy(update={"updated_at_ms": now_ms()})
        self.set_kv(_environment_settings_key(user_id), saved.model_dump())
        return saved

    def save_pet_action(self, action: PetAction) -> None:
        self.append("pet_action_log", action)
        self.append("event_log", EventData(event_type="pet_action_triggered", severity=action.priority, message=action.message, payload=action.model_dump()))

    def save_trace(self, trace: dict[str, Any]) -> None:
        self.append("agent_trace_log", trace)

    def save_daily_report(self, report: BaseModel) -> None:
        self.append("daily_report_log", report)
        self.append("event_log", EventData(event_type="daily_report_generated", severity="info", message="今日健康日报已生成"))

    def save_memory(self, summary: str) -> None:
        self.append("memory_log", {"summary": summary})

    def get_memory_summary(self) -> str:
        with connect(self.db_path) as conn:
            row = conn.execute("SELECT payload_json FROM memory_log ORDER BY id DESC LIMIT 1").fetchone()
        if not row:
            return ""
        return json.loads(row["payload_json"]).get("summary", "")

    def today_summary(self) -> TodaySummary:
        """基于已有事件和状态生成今日摘要，不编造未记录的数据。"""

        events = self.get_recent_events(limit=200)
        current = self.get_current_state()
        summary = TodaySummary(date=date.today().isoformat())
        for event in events:
            if event.event_type == "sedentary_warning":
                summary.sedentary_warning_count += 1
            elif event.event_type == "hydration_warning":
                summary.hydration_warning_count += 1
            elif event.event_type == "environment_warning":
                summary.environment_warning_count += 1
            elif event.event_type == "pet_action_triggered":
                summary.pet_action_count += 1
        if current:
            summary.drink_total_ml = current.drink_today_ml
            summary.longest_sedentary_minutes = current.sedentary_minutes
        return summary

    def set_kv(self, key: str, value: Any) -> None:
        with connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO kv_store (key, value_json) VALUES (?, ?)",
                (key, json.dumps(value, ensure_ascii=False)),
            )
            conn.commit()

    def get_kv(self, key: str, default: Any = None) -> Any:
        with connect(self.db_path) as conn:
            row = conn.execute("SELECT value_json FROM kv_store WHERE key = ?", (key,)).fetchone()
        if not row:
            return default
        return json.loads(row["value_json"])


def _environment_settings_key(user_id: str) -> str:
    safe_user_id = user_id.strip() or "default"
    return f"{ENVIRONMENT_SETTINGS_KEY_PREFIX}:{safe_user_id}"
