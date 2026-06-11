from __future__ import annotations

from app.agent_runtimes.settings import load_runtime_settings
from app.simulation.simulator import HealthSimulator
from app.storage.repository import HealthRepository


repo = HealthRepository(load_runtime_settings().database_path)
simulator = HealthSimulator()
