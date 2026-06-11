from __future__ import annotations

import os
import sqlite3
from pathlib import Path


DEFAULT_DB_PATH = os.getenv("HEALTHDESK_DB_PATH", "healthdesk.db")


def connect(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """创建 SQLite 连接，并开启 Row 字典式访问，方便 Repository 解析。"""

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """初始化数据库表结构。所有业务数据都以 JSON 形式保存，降低原型复杂度。"""

    conn = connect(db_path)
    try:
        cur = conn.cursor()
        for table in [
            "raw_log",
            "feature_log",
            "event_log",
            "state_log",
            "agent_trace_log",
            "daily_report_log",
            "memory_log",
            "pet_action_log",
        ]:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at_ms INTEGER NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
        cur.execute("CREATE TABLE IF NOT EXISTS kv_store (key TEXT PRIMARY KEY, value_json TEXT NOT NULL)")
        conn.commit()
    finally:
        conn.close()
