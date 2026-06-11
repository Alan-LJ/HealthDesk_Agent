"""规则 Skill 模块。

旧的 `*_skill.py` 仍作为受控编排 baseline 使用；新的 Skill Package 位于
`app/skills/<skill_name>/`，包含 SKILL.md、schemas.py 和 handler.py。
"""

from app.skills.skill_package import SKILL_PACKAGE_NAMES, load_skill_markdown, skill_package_dir

__all__ = ["SKILL_PACKAGE_NAMES", "load_skill_markdown", "skill_package_dir"]
