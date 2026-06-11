# Sedentary Analysis Skill

## 用途

判断当前办公状态是否存在久坐风险，并给出非医疗化的办公习惯建议。

## 触发条件

- 当前状态显示用户正在坐着。
- `sedentary_minutes` 达到 45 分钟或以上。
- 用户询问久坐、肩颈、腰背、站起活动或伸展提醒。
- Agent 需要判断是否生成桌宠伸展提醒。

## 输入

- `sedentary_minutes`: 连续坐姿分钟数，必须来自当前状态工具或 AIContext。
- `posture_change_level`: 坐姿变化水平，取值通常为 `low` / `medium` / `high`。
- `last_reminder_minutes_ago`: 距离上次提醒的分钟数。
- `device_confidence`: 座椅或姿态相关数据可信度。

## 输出

- `risk_level`: `none` / `low` / `medium` / `high`。
- `should_remind`: 是否建议触发提醒。
- `reason`: 可解释原因。
- `suggested_action`: 温和、可执行的办公习惯建议。

## 禁止事项

- 不输出医疗诊断。
- 不把腰痛、颈椎病等疾病判断写成结论。
- 设备可信度低于 0.6 时，不输出强提醒。
- 不使用 RAG 内容替代当前用户状态。

## 示例

输入：`sedentary_minutes=95, posture_change_level=low, device_confidence=0.9`

输出：高风险久坐提醒，建议站起活动 2 到 3 分钟。
