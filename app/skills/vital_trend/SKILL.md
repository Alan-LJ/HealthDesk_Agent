# Vital Trend Skill

## 用途

对呼吸和心率数据做办公状态趋势参考，不提供医疗诊断。

## 触发条件

- 用户询问呼吸、心率、生命体征趋势或设备可信度。
- 当前状态包含 `breath_rate_bpm` 或 `heart_rate_bpm`。
- Agent 需要判断生命体征数据是否可用于办公习惯建议。

## 输入

- `breath_rate_bpm`: 呼吸频率，可为空。
- `heart_rate_bpm`: 心率，可为空。
- `vital_quality`: 数据质量，低质量时必须降级。

## 输出

- `trend_summary`: 趋势参考说明。
- `can_use_for_advice`: 是否可用于办公习惯建议。
- `reason`: 数据质量或缺失原因。

## 禁止事项

- 禁止输出“心率异常”。
- 禁止输出“可能患病”“诊断为”“必须就医”“需要治疗”。
- `vital_quality=low` 时，只允许说明数据质量不足，暂不分析趋势。
- 不基于低可信数据生成强提醒。

## 示例

输入：`vital_quality=low`

输出：数据质量不足，暂不分析趋势。
