# Environment Comfort Skill

## 用途

根据温度和湿度判断办公环境舒适度，并优先按用户设置的适宜区间与重点监测阈值给出非医疗化的环境调整建议。

## 触发条件

- 用户询问温度、湿度、干燥、闷热、通风或空调。
- 当前状态显示温度或湿度偏离用户设置的适宜范围。
- 当前状态触达用户设置的温湿度重点监测阈值。
- Agent 需要判断是否生成环境舒适度提醒。

## 输入

- `temperature_c`: 当前温度，来自状态工具或 AIContext。
- `humidity_percent`: 当前湿度，来自状态工具或 AIContext。
- 用户环境设置：来自 `/settings/environment` 或 Repository，包括温湿度适宜区间、低/高温重点监测阈值、低/高湿重点监测阈值；如果未设置，使用默认办公区间。

## 输出

- `comfort_status`: `comfortable` / `dry` / `hot` / `cold` / `humid` / `mixed` 等。
- `alert_level`: `none` / `watch` / `warning`，用于区分适宜、轻微偏离和重点监测。
- `reason`: 触发判断的温湿度事实，并尽量说明“相对你的适宜区间”或“相对重点监测阈值”。
- `suggested_action`: 环境微调建议。

## 禁止事项

- 不把环境不适解释为疾病或症状。
- 不使用 RAG 替代当前传感器状态。
- 不输出恐吓式提醒。
- 不把个体敏感偏好描述成医学诊断，只表达为用户自定义环境偏好。

## 示例

输入：`temperature_c=29, humidity_percent=30`

输出：环境偏干或偏热；如果触达重点监测阈值，说明相对用户阈值的偏离，并建议补水、通风或微调空调。
