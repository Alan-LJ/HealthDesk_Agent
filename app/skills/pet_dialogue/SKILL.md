# Pet Dialogue Skill

## 用途

把健康风险标签转换为桌宠情绪、动画、话术和提醒优先级。

## 触发条件

- Health Agent 已经得到风险标签和建议动作。
- 用户需要桌宠提醒或互动反馈。
- Agent 需要把健康分析结果转换为可执行桌宠动作。

## 输入

- `risk_tags`: 风险标签，例如 `sedentary`、`hydration`、`environment`、`device`。
- `risk_level`: 总体风险等级。
- `user_tone`: 用户偏好语气，支持 `cute` / `gentle` / `professional`。
- `suggested_action`: 要传达给用户的温和建议。
- 当风险标签包含 `environment` 时，话术应优先承接环境 Skill 给出的“你的适宜区间”或“重点监测阈值”描述，不额外推断症状或疾病。

## 输出

- `emotion`: 桌宠情绪。
- `animation`: 桌宠动画。
- `message`: 气泡话术。
- `priority`: 提醒优先级。

## 禁止事项

- 不输出医疗诊断或疾病判断。
- 不使用命令式、恐吓式话术。
- 低置信度场景下不生成强打断动作。
- 桌宠消息必须温和、可中断、可解释。
- 环境提醒应表达为办公环境微调建议，避免把用户敏感偏好说成医学结论。

## 示例

输入：`risk_tags=["hydration"], risk_level="medium", user_tone="gentle"`

输出：饮水动画和温和补水提醒。
