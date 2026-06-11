from __future__ import annotations

from collections import deque
from typing import Deque

from app.schemas.event import EventData


class SlidingWindowMemory:
    """保存最近 N 条事件的内存窗口，适合做短期上下文。"""

    def __init__(self, max_items: int = 20) -> None:
        self.items: Deque[EventData] = deque(maxlen=max_items)

    def add_events(self, events: list[EventData]) -> None:
        for event in events:
            self.items.append(event)

    def recent(self) -> list[EventData]:
        return list(self.items)
