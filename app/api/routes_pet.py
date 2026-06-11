from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.agent_runtimes.settings import _load_env_file


router = APIRouter(tags=["pet"])
PET_DASHBOARD_PAGE = Path(__file__).resolve().parents[1] / "static" / "pet" / "index.html"
PET_COMPANION_PAGE = Path(__file__).resolve().parents[1] / "static" / "pet" / "companion.html"
PET_ASSET_DIR = Path(__file__).resolve().parents[2] / "pics"
PET_ASSETS = {
    "corgi_normal.png": PET_ASSET_DIR / "corgi_normal.png",
    "corgi_ears_up.png": PET_ASSET_DIR / "corgi_ears_up.png",
}


def _configured_pet_page() -> Path:
    _load_env_file()
    view = os.getenv("HEALTHDESK_PET_VIEW", "dashboard").strip().lower()
    if view in {"companion", "chat", "lite", "minimal"}:
        return PET_COMPANION_PAGE
    return PET_DASHBOARD_PAGE


@router.get("/")
def root_page() -> FileResponse:
    return FileResponse(_configured_pet_page())


@router.get("/pet")
def pet_page() -> FileResponse:
    return FileResponse(_configured_pet_page())


@router.get("/pet/dashboard")
def pet_dashboard_page() -> FileResponse:
    return FileResponse(PET_DASHBOARD_PAGE)


@router.get("/pet/companion")
def pet_companion_page() -> FileResponse:
    return FileResponse(PET_COMPANION_PAGE)


@router.get("/pet/assets/{asset_name}")
def pet_asset(asset_name: str) -> FileResponse:
    asset = PET_ASSETS.get(asset_name)
    if asset is None or not asset.exists():
        raise HTTPException(status_code=404, detail="pet asset not found")
    return FileResponse(asset)
