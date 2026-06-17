from __future__ import annotations

from fastapi import APIRouter

from app.main_state import repo
from app.schemas.environment import EnvironmentThresholdSettings


router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/environment")
def get_environment_settings(user_id: str = "default") -> dict:
    """读取用户温湿度适宜区间和重点监测阈值。"""

    return repo.get_environment_settings(user_id).model_dump()


@router.put("/environment")
def update_environment_settings(settings: EnvironmentThresholdSettings, user_id: str = "default") -> dict:
    """保存用户温湿度适宜区间和重点监测阈值。"""

    return repo.save_environment_settings(settings, user_id).model_dump()
