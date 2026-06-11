"""久坐 Skill 的输入输出模型。

第四步先复用旧单文件 Skill 的 Pydantic 模型，避免破坏旧受控编排链路。
"""

from app.skills.sedentary_skill import SedentaryInput, SedentaryOutput

__all__ = ["SedentaryInput", "SedentaryOutput"]
