from app.graph.state import create_initial_agent_state
from app.graph.trace_adapter import append_trace_step, build_trace_payload


def test_trace_payload_tolerates_malformed_tool_calls():
    state = create_initial_agent_state(task="trace robustness", user_id="u1")
    state["tool_calls"] = [
        "unexpected",
        {"name": "get_current_state", "tool_args": {}},
        {"tool_name": "analyze_environment_comfort", "tool_args": {}},
    ]

    payload = build_trace_payload(state, graph_name="test_graph", started_at=10, ended_at=15)

    assert payload["tools_called"] == ["get_current_state", "analyze_environment_comfort"]
    assert payload["tool_calls"][0]["raw"] == "unexpected"
    assert payload["latency_ms"] == 5


def test_append_trace_step_normalizes_non_string_summary_and_args():
    state = create_initial_agent_state(task="trace step robustness", user_id="u1")

    append_trace_step(
        state,
        node_name="node",
        action_type="action",
        tool_args=["not", "a", "dict"],  # type: ignore[arg-type]
        observation_summary={"summary": "ok"},  # type: ignore[arg-type]
    )

    step = state["trace_steps"][0]
    assert step["tool_args"] == {}
    assert step["observation_summary"] == "{'summary': 'ok'}"
