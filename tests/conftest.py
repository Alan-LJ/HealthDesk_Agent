import os
import tempfile
from pathlib import Path


TEST_DB_PATH = Path(tempfile.mkdtemp(prefix="healthdesk_agent_tests_")) / "healthdesk_agent_tests.db"
TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HEALTHDESK_DB_PATH", str(TEST_DB_PATH))
os.environ.setdefault("DATABASE_PATH", str(TEST_DB_PATH))
