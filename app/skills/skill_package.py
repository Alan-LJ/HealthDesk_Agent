from __future__ import annotations

from pathlib import Path


SKILL_PACKAGE_NAMES = [
    "sedentary",
    "hydration",
    "environment",
    "vital_trend",
    "pet_dialogue",
    "daily_report",
    "device_guardian",
    "web_realtime",
]


def skill_package_dir(skill_name: str) -> Path:
    """返回某个 Skill Package 的目录。

    后续 tool binding 会用这个路径读取 SKILL.md，把触发条件、输入输出和禁止事项
    吸收到模型可见的 tool description 中。
    """

    return Path(__file__).resolve().parent / skill_name


def load_skill_markdown(skill_name: str) -> str:
    """读取 Skill Package 的 SKILL.md。

    如果文件不存在，抛出清晰异常，避免第五步创建 tool description 时悄悄丢失
    Skill 说明书。
    """

    path = skill_package_dir(skill_name) / "SKILL.md"
    if not path.exists():
        raise FileNotFoundError(f"Skill package 缺少 SKILL.md: {skill_name}")
    return path.read_text(encoding="utf-8")
