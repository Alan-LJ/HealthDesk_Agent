# Environment Comfort Skill

## 用途

根据温度和湿度判断办公环境舒适度，并给出非医疗化的环境调整建议。

## 触发条件

- 用户询问温度、湿度、干燥、闷热、通风或空调。
- 当前状态显示温度或湿度偏离舒适范围。
- Agent 需要判断是否生成环境舒适度提醒。

## 输入

- `temperature_c`: 当前温度，来自状态工具或 AIContext。
- `humidity_percent`: 当前湿度，来自状态工具或 AIContext。

## 输出

- `comfort_status`: `comfortable` / `dry` / `hot` / `cold` / `humid` / `mixed` 等。
- `reason`: 触发判断的温湿度事实。
- `suggested_action`: 环境微调建议。

## 禁止事项

- 不把环境不适解释为疾病或症状。
- 不使用 RAG 替代当前传感器状态。
- 不输出恐吓式提醒。

## 示例

输入：`temperature_c=29, humidity_percent=30`

输出：环境偏干或偏热，建议补水、通风或微调空调。
