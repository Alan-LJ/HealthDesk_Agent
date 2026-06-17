from __future__ import annotations

from typing import Any

from app.agent_tools.realtime_tools import build_realtime_tools
from app.skills.web_realtime import WeatherInput, WebRealtimeSkillHandler, WebSearchInput


class FakeOpenMeteoClient:
    def get_json(self, url: str, params: dict[str, Any], headers: dict[str, str] | None = None) -> dict[str, Any]:
        if "geocoding-api" in url:
            return {
                "results": [
                    {
                        "name": "杭州",
                        "latitude": 30.25,
                        "longitude": 120.16,
                        "country": "中国",
                        "admin1": "浙江省",
                        "timezone": "Asia/Shanghai",
                    }
                ]
            }
        if "air-quality-api" in url:
            return {"current": {"us_aqi": 42, "pm2_5": 9.5, "pm10": 18.0, "uv_index": 3.2}}
        return {
            "timezone": "Asia/Shanghai",
            "current": {
                "time": "2026-06-17T14:45",
                "temperature_2m": 29.1,
                "relative_humidity_2m": 58,
                "apparent_temperature": 31.0,
                "precipitation": 0.0,
                "weather_code": 2,
                "cloud_cover": 45,
                "wind_speed_10m": 12.4,
                "wind_direction_10m": 110,
                "wind_gusts_10m": 22.1,
            },
            "daily": {
                "time": ["2026-06-17"],
                "temperature_2m_max": [31.2],
                "temperature_2m_min": [24.8],
                "precipitation_probability_max": [30],
                "uv_index_max": [5.6],
            },
        }


def test_get_weather_uses_open_meteo_payload():
    handler = WebRealtimeSkillHandler(client=FakeOpenMeteoClient(), brave_api_key="")

    result = handler.get_weather(WeatherInput(location="杭州"))

    assert result.status == "ok"
    assert result.resolved_name == "杭州"
    assert result.temperature_c == 29.1
    assert result.humidity_percent == 58
    assert result.weather_description == "多云"
    assert result.air_quality["pm2_5"] == 9.5
    assert "open-meteo-air-quality" in result.data_sources


def test_search_web_without_provider_returns_unavailable_observation():
    handler = WebRealtimeSkillHandler(client=FakeOpenMeteoClient(), brave_api_key="")

    result = handler.search_web(WebSearchInput(query="今天科技新闻", top_k=3))

    assert result.status == "unavailable"
    assert result.provider == "brave"
    assert result.results == []
    assert "BRAVE_SEARCH_API_KEY" in result.summary


def test_realtime_tools_return_tool_observations():
    tools = {tool.name: tool for tool in build_realtime_tools(WebRealtimeSkillHandler(client=FakeOpenMeteoClient(), brave_api_key=""))}

    weather = tools["get_weather"].invoke({"location": "杭州"})
    search = tools["search_web"].invoke({"query": "今天科技新闻"})

    assert weather.success is True
    assert weather.raw_data["status"] == "ok"
    assert weather.metadata["skill"] == "web_realtime"
    assert search.success is True
    assert search.raw_data["status"] == "unavailable"
