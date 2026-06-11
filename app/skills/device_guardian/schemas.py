"""设备守护 Skill 的输入输出模型。"""

from app.schemas.agent_outputs import DeviceGuardianOutput
from app.skills.device_guardian_skill import DeviceGuardianInput

__all__ = ["DeviceGuardianInput", "DeviceGuardianOutput"]
