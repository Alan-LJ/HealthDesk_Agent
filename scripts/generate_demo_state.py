from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.simulation.simulator import HealthSimulator
from app.agent_runtimes.settings import load_runtime_settings
from app.storage.repository import HealthRepository


if __name__ == "__main__":
    repo = HealthRepository(load_runtime_settings().database_path)
    simulator = HealthSimulator()
    for scenario in ["normal_work", "sedentary_high", "low_hydration", "dry_environment", "mixed_risk"]:
        simulator.set_scenario(scenario)
        tick = simulator.tick()
        repo.save_tick(tick.raw, tick.feature, tick.state, tick.events, tick.sensor_health)
    print("已生成一组模拟办公日数据")
