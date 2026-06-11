from pathlib import Path

from app.schemas.common import SensorHealth, TodaySummary
from app.skills import SKILL_PACKAGE_NAMES, load_skill_markdown, skill_package_dir
from app.skills.daily_report import DailyReportInput, DailyReportSkillHandler
from app.skills.device_guardian import DeviceGuardianInput, DeviceGuardianSkillHandler
from app.skills.environment import EnvironmentInput, EnvironmentSkillHandler
from app.skills.hydration import HydrationInput, HydrationSkillHandler
from app.skills.pet_dialogue import PetDialogueInput, PetDialogueSkillHandler
from app.skills.sedentary import SedentaryInput, SedentarySkillHandler
from app.skills.vital_trend import VitalTrendInput, VitalTrendSkillHandler


def test_each_skill_package_has_required_files_and_sections():
    required = {"SKILL.md", "schemas.py", "handler.py"}
    required_sections = ["触发条件", "输入", "输出", "禁止事项"]

    for skill_name in SKILL_PACKAGE_NAMES:
        package_dir = skill_package_dir(skill_name)
        assert package_dir.exists(), skill_name
        assert required.issubset({path.name for path in package_dir.iterdir()}), skill_name
        text = load_skill_markdown(skill_name)
        for section in required_sections:
            assert section in text, f"{skill_name} 缺少 {section}"


def test_skill_package_handlers_reuse_existing_rules():
    sedentary = SedentarySkillHandler().run(SedentaryInput(sedentary_minutes=95, posture_change_level="low", device_confidence=0.9))
    hydration = HydrationSkillHandler().run(HydrationInput(drink_today_ml=300, last_drink_minutes_ago=150, humidity_percent=25, temperature_c=29))
    environment = EnvironmentSkillHandler().run(EnvironmentInput(temperature_c=29, humidity_percent=30))
    vital = VitalTrendSkillHandler().run(VitalTrendInput(vital_quality="low"))
    pet = PetDialogueSkillHandler().run(PetDialogueInput(risk_tags=["sedentary"], risk_level="high", suggested_action="站起活动 2 到 3 分钟"))

    assert sedentary.risk_level == "high"
    assert hydration.risk_level == "high"
    assert environment.comfort_status in {"dry", "hot"}
    assert vital.can_use_for_advice is False
    assert pet.animation == "stretch"


def test_report_and_device_guardian_handlers_reuse_existing_rules():
    report = DailyReportSkillHandler().run(
        DailyReportInput(
            today_summary=TodaySummary(date="2026-06-08", sedentary_warning_count=1, drink_total_ml=500),
            recent_events=[],
            memory_summary="今天下午出现久坐提醒",
        )
    )
    device = DeviceGuardianSkillHandler().run(
        DeviceGuardianInput(
            sensor_health=[
                SensorHealth(device_id="sim_vital_001", module="vital", online=True, confidence=0.4),
            ],
            device_confidence=0.5,
        )
    )

    assert "办公健康日报" in report.report_title
    assert report.suggestions
    assert device.system_status == "degraded"
    assert "vital" in device.degraded_modules


def test_load_skill_markdown_raises_for_missing_skill():
    missing = skill_package_dir("missing_skill") / "SKILL.md"
    assert not Path(missing).exists()
    try:
        load_skill_markdown("missing_skill")
    except FileNotFoundError as exc:
        assert "missing_skill" in str(exc)
    else:
        raise AssertionError("missing skill should raise FileNotFoundError")
