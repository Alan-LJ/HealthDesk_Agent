# Hydration Analysis Skill

## 用途

判断当前办公状态是否需要饮水提醒，并结合环境干燥程度调整提醒优先级。

## 触发条件

- 今日饮水量偏低。
- 距离上次饮水时间较久。
- 当前环境湿度偏低或温度偏高。
- 用户询问喝水、口渴、补水或桌宠饮水提醒。

## 输入

- `drink_today_ml`: 今日累计饮水量，必须来自当前状态或今日统计。
- `last_drink_minutes_ago`: 距离上次饮水的分钟数。
- `humidity_percent`: 当前湿度。
- `temperature_c`: 当前温度。

## 输出

- `risk_level`: 饮水提醒等级。
- `should_remind`: 是否需要提醒。
- `reason`: 事实依据。
- `suggested_action`: 温和补水建议。

## 禁止事项

- 不输出医疗或营养治疗建议。
- 不要求用户一次性大量饮水。
- 不用 RAG 片段推断今日真实饮水量。
- 对数据缺失或低可信情况应降低提醒强度。

## 示例

输入：`drink_today_ml=300, last_drink_minutes_ago=150, humidity_percent=25`

输出：饮水提醒优先级升高，建议喝几口水并关注环境干燥。
