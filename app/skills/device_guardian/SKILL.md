# Device Guardian Skill

## 用途

检查模拟传感器和数据可信状态，告诉 Agent 哪些建议必须降级。

## 触发条件

- 当前 sensor health 显示设备离线、数据过期或置信度低。
- `device_confidence` 低于 0.6。
- 用户询问设备、传感器、数据可信度或为什么提醒变弱。
- Health Agent 准备基于低可信数据输出建议前。

## 输入

- `sensor_health`: 传感器健康列表。
- `device_confidence`: 当前整体设备置信度。
- `last_seen_seconds`: 数据最后出现时间。
- `error_codes`: 错误码列表。

## 输出

- `system_status`: `healthy` 或 `degraded`。
- `degraded_modules`: 降级模块。
- `impact`: 对建议强度的影响。
- `user_message`: 给用户的解释。

## 禁止事项

- 不把低置信度数据包装成强结论。
- 不输出医疗诊断。
- 不隐藏设备降级事实。
- 当设备不可信时，必须告诉 Agent 哪些建议只能作为参考。

## 示例

输入：某生命体征模块置信度 0.4。

输出：该模块相关建议降级为参考，不生成强提醒。
