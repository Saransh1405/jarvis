from jarvis_ai.llm.agent_types import AgentTurn, ToolCall
from jarvis_ai.llm.gemini_provider import (
    _inject_skip_thought_signature,
    _prepare_messages_for_gemini,
    _thought_signature_present,
)
from jarvis_ai.llm.messages import append_assistant_turn


def test_thought_signature_detected():
    calls = [
        {
            "id": "1",
            "type": "function",
            "extra_content": {"google": {"thought_signature": "abc"}},
            "function": {"name": "calculator", "arguments": "{}"},
        }
    ]
    assert _thought_signature_present(calls) is True


def test_inject_skip_on_missing_signature():
    calls = [
        {
            "id": "1",
            "type": "function",
            "function": {"name": "calculator", "arguments": '{"expression":"2+2"}'},
        }
    ]
    fixed = _inject_skip_thought_signature(calls)
    assert fixed[0]["extra_content"]["google"]["thought_signature"] == "skip_thought_signature_validator"


def test_prepare_messages_repairs_assistant_tool_calls():
    messages = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "1",
                    "type": "function",
                    "function": {"name": "calculator", "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "1", "content": "4"},
    ]
    out = _prepare_messages_for_gemini(messages)
    assert (
        out[0]["tool_calls"][0]["extra_content"]["google"]["thought_signature"]
        == "skip_thought_signature_validator"
    )


def test_append_assistant_turn_preserves_payloads():
    messages: list[dict] = []
    turn = AgentTurn(
        tool_calls=[ToolCall(id="1", name="calculator", arguments={"expression": "1+1"})],
        tool_call_payloads=[
            {
                "id": "1",
                "type": "function",
                "extra_content": {"google": {"thought_signature": "real-sig"}},
                "function": {"name": "calculator", "arguments": '{"expression":"1+1"}'},
            }
        ],
    )
    append_assistant_turn(messages, turn)
    assert messages[0]["tool_calls"][0]["extra_content"]["google"]["thought_signature"] == "real-sig"
