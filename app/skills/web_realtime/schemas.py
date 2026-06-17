"""实时网络信息 Skill 的输入输出模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


RealtimeStatus = Literal["ok", "not_found", "unavailable", "error"]


class WeatherInput(BaseModel):
    location: str = Field(description="城市、地区或邮编，例如 Hangzhou、杭州、San Francisco, CA")
    language: str = Field(default="zh", description="地理编码返回语言，默认中文")
    country_code: str | None = Field(default=None, description="可选 ISO-3166-1 alpha2 国家代码，例如 CN、US")
    include_air_quality: bool = Field(default=True, description="是否同时查询 PM2.5、AQI 等空气质量指标")


class WeatherOutput(BaseModel):
    status: RealtimeStatus
    location_query: str
    resolved_name: str | None = None
    country: str | None = None
    admin1: str | None = None
    timezone: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    current_time: str | None = None
    temperature_c: float | None = None
    humidity_percent: float | None = None
    apparent_temperature_c: float | None = None
    precipitation_mm: float | None = None
    weather_code: int | None = None
    weather_description: str | None = None
    cloud_cover_percent: float | None = None
    wind_speed_kmh: float | None = None
    wind_direction_deg: float | None = None
    wind_gusts_kmh: float | None = None
    today: dict[str, Any] = Field(default_factory=dict)
    air_quality: dict[str, Any] = Field(default_factory=dict)
    summary: str
    data_sources: list[str] = Field(default_factory=list)


class WebSearchInput(BaseModel):
    query: str
    top_k: int = Field(default=3, ge=1, le=10)


class WebSearchResult(BaseModel):
    title: str
    url: str
    snippet: str = ""
    published_at: str | None = None


class WebSearchOutput(BaseModel):
    status: RealtimeStatus
    query: str
    provider: str
    results: list[WebSearchResult] = Field(default_factory=list)
    summary: str
    data_sources: list[str] = Field(default_factory=list)
