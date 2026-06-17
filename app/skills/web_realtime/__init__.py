"""实时网络信息 Skill Package。"""

from app.skills.web_realtime.handler import WebRealtimeSkillHandler, get_weather, search_web
from app.skills.web_realtime.schemas import WeatherInput, WeatherOutput, WebSearchInput, WebSearchOutput, WebSearchResult

__all__ = [
    "WeatherInput",
    "WeatherOutput",
    "WebSearchInput",
    "WebSearchOutput",
    "WebSearchResult",
    "WebRealtimeSkillHandler",
    "get_weather",
    "search_web",
]
