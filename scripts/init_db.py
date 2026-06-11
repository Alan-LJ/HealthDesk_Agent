from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent_runtimes.settings import load_runtime_settings
from app.storage.db import init_db


if __name__ == "__main__":
    db_path = load_runtime_settings().database_path
    init_db(db_path)
    print(f"SQLite 数据库已初始化: {db_path}")
