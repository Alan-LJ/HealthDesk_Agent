from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Protocol

from app.skills.web_realtime.schemas import (
    WeatherInput,
    WeatherOutput,
    WebSearchInput,
    WebSearchOutput,
    WebSearchResult,
)


OPEN_METEO_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
HTTP_TIMEOUT_SECONDS = 8


class JsonHttpClient(Protocol):
    def get_json(self, url: str, params: dict[str, Any], headers: dict[str, str] | None = None) -> dict[str, Any]:
        ...


class UrlLibJsonHttpClient:
    def get_json(self, url: str, params: dict[str, Any], headers: dict[str, str] | None = None) -> dict[str, Any]:
        query = urllib.parse.urlencode({key: value for key, value in params.items() if value is not None})
        request = urllib.request.Request(f"{url}?{query}", headers=headers or {"Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                text = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code}: {body[:200]}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"网络请求失败: {exc.reason}") from exc
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"接口返回了无法解析的 JSON: {text[:120]}") from exc
        if not isinstance(data, dict):
            raise RuntimeError("接口返回 JSON 不是对象")
        return data


class WebRealtimeSkillHandler:
    """实时网络信息 Skill。

    Open-Meteo 查询不需要 API key；通用搜索默认使用 Brave Search，需要配置
    BRAVE_SEARCH_API_KEY。未配置时返回 unavailable observation，而不是让 Agent 编造。
    """

    def __init__(self, client: JsonHttpClient | None = None, brave_api_key: str | None = None) -> None:
        self.client = client or UrlLibJsonHttpClient()
        self.brave_api_key = brave_api_key if brave_api_key is not None else os.getenv("BRAVE_SEARCH_API_KEY", "")

    def get_weather(self, data: WeatherInput) -> WeatherOutput:
        location = data.location.strip()
        if not location:
            return WeatherOutput(status="not_found", location_query=data.location, summary="请提供要查询天气的城市或地区。")
        try:
            place = self._resolve_location(data)
            if place is None:
                return WeatherOutput(
                    status="not_found",
                    location_query=data.location,
                    summary=f"没有找到“{data.location}”对应的城市位置，请补充城市、省份或国家。",
                    data_sources=["open-meteo-geocoding"],
                )
            forecast = self._fetch_forecast(place)
            air_quality = self._fetch_air_quality(place) if data.include_air_quality else {}
            return _build_weather_output(data, place, forecast, air_quality)
        except RuntimeError as exc:
            return WeatherOutput(
                status="error",
                location_query=data.location,
                summary=f"天气服务暂时不可用：{exc}",
                data_sources=["open-meteo"],
            )

    def search_web(self, data: WebSearchInput) -> WebSearchOutput:
        query = data.query.strip()
        if not query:
            return WebSearchOutput(status="not_found", query=data.query, provider="none", summary="请提供要搜索的关键词。")
        if not self.brave_api_key:
            return WebSearchOutput(
                status="unavailable",
                query=query,
                provider="brave",
                summary="通用网页搜索尚未配置 BRAVE_SEARCH_API_KEY；天气类实时问题请优先调用 get_weather。",
            )
        try:
            payload = self.client.get_json(
                BRAVE_SEARCH_URL,
                {"q": query, "count": data.top_k},
                headers={"Accept": "application/json", "X-Subscription-Token": self.brave_api_key},
            )
        except RuntimeError as exc:
            return WebSearchOutput(status="error", query=query, provider="brave", summary=f"网页搜索暂时不可用：{exc}")
        results = []
        for item in (payload.get("web") or {}).get("results", [])[: data.top_k]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            url = str(item.get("url") or "").strip()
            if not title or not url:
                continue
            results.append(
                WebSearchResult(
                    title=title,
                    url=url,
                    snippet=str(item.get("description") or ""),
                    published_at=item.get("age") if isinstance(item.get("age"), str) else None,
                )
            )
        summary = f"搜索到 {len(results)} 条网页结果。" if results else "没有搜索到可用网页结果。"
        return WebSearchOutput(
            status="ok" if results else "not_found",
            query=query,
            provider="brave",
            results=results,
            summary=summary,
            data_sources=[item.url for item in results],
        )

    def _resolve_location(self, data: WeatherInput) -> dict[str, Any] | None:
        params = {
            "name": data.location,
            "count": 1,
            "language": data.language,
            "format": "json",
            "countryCode": data.country_code,
        }
        payload = self.client.get_json(OPEN_METEO_GEOCODING_URL, params)
        results = payload.get("results")
        if not isinstance(results, list) or not results:
            return None
        first = results[0]
        return first if isinstance(first, dict) else None

    def _fetch_forecast(self, place: dict[str, Any]) -> dict[str, Any]:
        return self.client.get_json(
            OPEN_METEO_FORECAST_URL,
            {
                "latitude": place.get("latitude"),
                "longitude": place.get("longitude"),
                "current": ",".join(
                    [
                        "temperature_2m",
                        "relative_humidity_2m",
                        "apparent_temperature",
                        "precipitation",
                        "weather_code",
                        "cloud_cover",
                        "wind_speed_10m",
                        "wind_direction_10m",
                        "wind_gusts_10m",
                    ]
                ),
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,uv_index_max",
                "forecast_days": 1,
                "timezone": "auto",
            },
        )

    def _fetch_air_quality(self, place: dict[str, Any]) -> dict[str, Any]:
        return self.client.get_json(
            OPEN_METEO_AIR_QUALITY_URL,
            {
                "latitude": place.get("latitude"),
                "longitude": place.get("longitude"),
                "current": "us_aqi,pm2_5,pm10,uv_index",
                "timezone": "auto",
            },
        )


def _build_weather_output(
    data: WeatherInput,
    place: dict[str, Any],
    forecast: dict[str, Any],
    air_quality_payload: dict[str, Any],
) -> WeatherOutput:
    current = forecast.get("current") if isinstance(forecast.get("current"), dict) else {}
    daily = _first_daily_values(forecast.get("daily") if isinstance(forecast.get("daily"), dict) else {})
    air_quality = air_quality_payload.get("current") if isinstance(air_quality_payload.get("current"), dict) else {}
    code = _as_int(current.get("weather_code"))
    description = _weather_code_description(code)
    name = str(place.get("name") or data.location)
    country = place.get("country") if isinstance(place.get("country"), str) else None
    admin1 = place.get("admin1") if isinstance(place.get("admin1"), str) else None
    temp = _as_float(current.get("temperature_2m"))
    humidity = _as_float(current.get("relative_humidity_2m"))
    air_summary = ""
    if air_quality:
        parts = []
        if air_quality.get("us_aqi") is not None:
            parts.append(f"US AQI {air_quality.get('us_aqi')}")
        if air_quality.get("pm2_5") is not None:
            parts.append(f"PM2.5 {air_quality.get('pm2_5')} μg/m³")
        if parts:
            air_summary = "，" + "，".join(parts)
    summary = f"{_location_label(name, admin1, country)}当前{description}"
    if temp is not None:
        summary += f"，气温 {temp:.1f}°C"
    if humidity is not None:
        summary += f"，湿度 {humidity:.0f}%"
    summary += air_summary + "。"
    return WeatherOutput(
        status="ok",
        location_query=data.location,
        resolved_name=name,
        country=country,
        admin1=admin1,
        timezone=forecast.get("timezone") if isinstance(forecast.get("timezone"), str) else place.get("timezone"),
        latitude=_as_float(place.get("latitude")),
        longitude=_as_float(place.get("longitude")),
        current_time=current.get("time") if isinstance(current.get("time"), str) else None,
        temperature_c=temp,
        humidity_percent=humidity,
        apparent_temperature_c=_as_float(current.get("apparent_temperature")),
        precipitation_mm=_as_float(current.get("precipitation")),
        weather_code=code,
        weather_description=description,
        cloud_cover_percent=_as_float(current.get("cloud_cover")),
        wind_speed_kmh=_as_float(current.get("wind_speed_10m")),
        wind_direction_deg=_as_float(current.get("wind_direction_10m")),
        wind_gusts_kmh=_as_float(current.get("wind_gusts_10m")),
        today=daily,
        air_quality=air_quality,
        summary=summary,
        data_sources=["open-meteo-geocoding", "open-meteo-forecast"]
        + (["open-meteo-air-quality"] if air_quality else []),
    )


def _first_daily_values(daily: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for key, value in daily.items():
        if isinstance(value, list) and value:
            values[key] = value[0]
        else:
            values[key] = value
    return values


def _location_label(name: str, admin1: str | None, country: str | None) -> str:
    parts = [name]
    if admin1 and admin1 not in parts:
        parts.append(admin1)
    if country and country not in parts:
        parts.append(country)
    return "、".join(parts)


def _as_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _as_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _weather_code_description(code: int | None) -> str:
    if code is None:
        return "天气状况未知"
    if code == 0:
        return "晴朗"
    if code in {1, 2, 3}:
        return "多云"
    if code in {45, 48}:
        return "有雾"
    if code in {51, 53, 55, 56, 57}:
        return "毛毛雨"
    if code in {61, 63, 65, 66, 67, 80, 81, 82}:
        return "降雨"
    if code in {71, 73, 75, 77, 85, 86}:
        return "降雪"
    if code in {95, 96, 99}:
        return "雷暴"
    return f"天气代码 {code}"


def get_weather(data: WeatherInput) -> WeatherOutput:
    return WebRealtimeSkillHandler().get_weather(data)


def search_web(data: WebSearchInput) -> WebSearchOutput:
    return WebRealtimeSkillHandler().search_web(data)
