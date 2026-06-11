# HealthDesk LangGraph + DeepSeek Agent

这是一个只保留真实 Agent pipeline 的办公健康 Agent 原型。

当前唯一技术路线：

```text
FastAPI /agent/run
-> LangGraphDeepSeekRuntime
-> LangGraph StateGraph
-> DeepSeek tool calling
-> Python tool handlers
-> ToolObservation
-> submit_final_output
-> HealthAgentFinalOutput
-> guardrails
-> SQLite trace
```

## 保留能力

- `LangGraph + DeepSeek` ReAct loop
- DeepSeek tool calling 作为真实 planner
- `AgentState` 显式运行态状态
- Context tools：当前状态、近期事件、今日统计、sensor health
- Analysis tools：久坐、饮水、环境、生命体征趋势、设备诊断
- RAG tools：本地 Markdown 知识依据
- Memory tools：用户摘要记忆
- Handoff tool：`HealthCoordinatorAgent -> DeviceGuardianAgent`
- Structured output：`HealthAgentFinalOutput`
- Guardrails：输出和桌宠动作医疗化表达检查
- Trace：tool calls、observations、RAG chunks、guardrail status、final output

## 快速运行

```powershell
cd P:\AI\HDA\healthdesk_agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

初始化并生成一条状态数据：

```powershell
python scripts\init_db.py
python scripts\generate_demo_state.py
```

启动服务：

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## DeepSeek 配置

`.env` / `.env.example` 只保留真实 Agent 所需配置：

```text
DEEPSEEK_API_KEY=XXX
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_THINKING=disabled
DEEPSEEK_REASONING_EFFORT=high
DATABASE_PATH=./healthdesk.db
MAX_AGENT_STEPS=6
MAX_SAME_TOOL_CALLS=2
RAG_TOP_K=3
TRACE_TO_SQLITE=true
```

## API

打开桌宠展示页：

```text
http://127.0.0.1:8000/pet
```

生成或切换模拟状态：

```powershell
curl -X POST http://127.0.0.1:8000/simulation/scenario/sedentary_high
curl -X POST http://127.0.0.1:8000/simulation/tick
curl http://127.0.0.1:8000/state/current
```

运行真实 Agent：

```powershell
curl -X POST http://127.0.0.1:8000/agent/run `
  -H "Content-Type: application/json" `
  -d "{\"task\":\"分析我当前办公健康状态，并生成桌宠提醒\",\"user_id\":\"default\"}"
```

查看 trace：

```powershell
curl http://127.0.0.1:8000/traces/recent
curl http://127.0.0.1:8000/traces/{trace_id}
```

## 文档

- [真实 Agent Pipeline](docs/16_langgraph_deepseek_interview.md)

## 验证

项目保留与真实 Agent pipeline 相关的测试：

```powershell
python -m pytest
```

## 桌宠展示模式

完整网页版展示：

```text
http://127.0.0.1:8000/pet/dashboard
```

浏览器内轻量桌宠对话页：

```text
http://127.0.0.1:8000/pet/companion
```

真实桌面自由拖动桌宠（不受浏览器窗口限制）：

```powershell
cd P:\AI\HDA\healthdesk_agent
.\scripts\run_desktop_companion.ps1
```

也可以直接运行：

```powershell
python -m app.desktop_companion
```

桌面版使用 `tkinter` 透明无边框窗口实现：`overrideredirect(True)` 去边框、`attributes("-topmost", True)` 置顶、`attributes("-transparentcolor", "#01FF01")` 色键透明，并通过 `geometry("+x+y")` 在桌面坐标系中实时拖动窗口。拖动范围基于 Windows 虚拟桌面坐标，可跨主屏/副屏移动。位置会保存到 `.hda/desktop_companion_position.json`，下次启动自动驻留在上次位置。
