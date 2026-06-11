from __future__ import annotations

from pydantic import BaseModel

from app.schemas.event import PetAction


class PetDialogueInput(BaseModel):
    risk_tags: list[str]
    risk_level: str
    user_tone: str = "gentle"
    suggested_action: str


class PetDialogueSkill:
    """桌宠话术 Skill，把风险标签转成可执行动作和温和提醒。"""

    def run(self, data: PetDialogueInput) -> PetAction:
        if "hydration" in data.risk_tags:
            animation = "drink_water"
        elif "sedentary" in data.risk_tags:
            animation = "stretch"
        elif "environment" in data.risk_tags:
            animation = "adjust_environment"
        elif "device" in data.risk_tags:
            animation = "check_device"
        else:
            animation = "idle"
        emotion = "concerned" if data.risk_level in {"medium", "high"} else "calm"
        templates = {
            "cute": f"我轻轻冒个泡：{data.suggested_action}",
            "gentle": f"给你一个温和提醒：{data.suggested_action}",
            "professional": f"办公健康提醒：{data.suggested_action}",
        }
        priority = "high" if data.risk_level == "high" else "medium" if data.risk_level == "medium" else "low"
        return PetAction(emotion=emotion, animation=animation, message=templates.get(data.user_tone, templates["gentle"]), priority=priority)
