from __future__ import annotations

from app.schemas.event import EventData


class RuleBasedMemorySummarizer:
    """规则版记忆摘要器，本阶段不依赖 LLM。"""

    def summarize(self, events: list[EventData]) -> str:
        """根据近期事件生成一句可读摘要，写入 SQLite 供 AI Context 使用。"""

        types = [event.event_type for event in events]
        parts: list[str] = []
        if "sedentary_warning" in types:
            parts.append("用户近期出现久坐提醒")
        if "hydration_warning" in types:
            parts.append("今日饮水提醒需要关注")
        if "environment_warning" in types:
            parts.append("办公环境舒适度有波动")
        if "device_degraded" in types:
            parts.append("存在设备低可信或离线情况")
        return "；".join(parts) if parts else "近期状态平稳，暂无明显风险事件"
