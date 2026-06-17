# Web Realtime Skill

## 用途

查询外部实时信息。当前第一阶段用于天气和空气质量查询，天气数据来自 Open-Meteo；通用网页搜索通过可配置搜索 provider 接入。

## 触发条件

- 用户询问某地当前天气、气温、湿度、降雨、风力、紫外线、PM2.5、空气质量等实时外部信息。
- 用户明确要求“联网查一下”“搜索最新信息”“查网页资料”。
- 用户问题依赖当前日期之后可能变化的信息，而本地 SQLite、AIContext、RAG 知识库无法提供事实来源。

## 输入

- `get_weather.location`: 城市、地区或邮编。
- `get_weather.include_air_quality`: 是否同步查询 AQI、PM2.5、PM10、UV 等空气质量指标。
- `search_web.query`: 通用网页搜索关键词。
- `search_web.top_k`: 返回结果数量，最多 10 条。

## 输出

- 天气输出包含解析后的地点、当前温度、湿度、体感温度、天气代码、风速、今日预报、空气质量和数据来源。
- 网页搜索输出包含 provider、结果标题、URL、摘要和数据来源。
- 当外部服务未配置或不可用时，返回 `status=unavailable` 或 `status=error`，由 Agent 用自然语言说明边界。

## 禁止事项

- 不要把模型自身知识当成实时天气或新闻事实。
- 不要用 RAG 健康知识库替代实时天气、空气质量或网页搜索。
- 未拿到工具结果时，不要编造温度、AQI、PM2.5、新闻、价格、政策等实时信息。
- 天气和空气质量结果只用于生活与办公环境参考，不输出医疗诊断或治疗建议。

## 示例

输入：`get_weather(location="杭州", include_air_quality=true)`

输出：返回杭州当前气温、湿度、天气状况、PM2.5/AQI，并说明数据来自 Open-Meteo。
