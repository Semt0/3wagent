"""Provider-specific textual tool calls are normalized at one boundary."""

from qwen_agent.llm.schema import ASSISTANT, FunctionCall, Message
from src.agent.tool_call_compat import (
    ToolCallCompatibilityMixin,
    normalize_textual_tool_calls,
)

DSML_RESPONSE = r"""I'll verify the official source.

<｜｜DSML｜｜ calls>
<｜｜DSML｜｜ invoke name="YamlReadTool">
<｜｜DSML｜｜ parameter name="arguments" string="false">{"file\_path": "config/output-contract.yaml"}\</｜｜DSML｜｜ parameter>
\</｜｜DSML｜｜ invoke>
<｜｜DSML｜｜ invoke name="WebSearchTool">
<｜｜DSML｜｜ parameter name="arguments" string="false">{"query": "境外上市备案", "limit": 8}\</｜｜DSML｜｜ parameter>
\</｜｜DSML｜｜ invoke>
\</｜｜DSML｜｜ calls>"""


def test_dsml_parallel_calls_become_native_function_calls():
    output = normalize_textual_tool_calls(
        [
            Message(
                ASSISTANT,
                DSML_RESPONSE,
                reasoning_content="Need official evidence.",
                name="3wagent",
            )
        ]
    )

    assert output[0].content == "I'll verify the official source."
    assert output[0].reasoning_content == "Need official evidence."
    assert [message.function_call.name for message in output[1:]] == [
        "YamlReadTool",
        "WebSearchTool",
    ]
    assert output[1].function_call.arguments == '{"file_path": "config/output-contract.yaml"}'
    assert output[2].function_call.arguments == '{"query": "境外上市备案", "limit": 8}'
    assert [message.extra["function_id"] for message in output[1:]] == ["1", "2"]


def test_native_function_call_passes_through_unchanged():
    message = Message(
        ASSISTANT,
        "",
        function_call=FunctionCall(name="WebFetchTool", arguments='{"url": "https://x"}'),
    )

    assert normalize_textual_tool_calls([message]) == [message]


def test_legacy_tool_call_tags_are_also_normalized():
    text = '''Checking now.
<tool_call>
{"name": "WebFetchTool", "arguments": {"url": "https://example.com"}}
</tool_call>'''

    output = normalize_textual_tool_calls([Message(ASSISTANT, text)])

    assert output[0].content == "Checking now."
    assert output[1].function_call.name == "WebFetchTool"
    assert output[1].function_call.arguments == '{"url": "https://example.com"}'


def test_reasoning_is_attached_to_tool_call_when_there_is_no_visible_prefix():
    text = (
        '<tool_call>{"name":"WebSearchTool",'
        '"arguments":{"query":"test"}}</tool_call>'
    )

    output = normalize_textual_tool_calls(
        [Message(ASSISTANT, text, reasoning_content="Need to search.")]
    )

    assert output[0].function_call.name == "WebSearchTool"
    assert output[0].reasoning_content == "Need to search."


def test_incomplete_dsml_stays_non_executable_text():
    message = Message(ASSISTANT, '<｜｜DSML｜｜ invoke name="WebSearchTool">')

    assert normalize_textual_tool_calls([message]) == [message]


def test_boundary_only_normalizes_when_tools_are_enabled():
    class FakeBoundary:
        def _call_llm(self, **kwargs):
            yield [Message(ASSISTANT, DSML_RESPONSE)]

    class CompatibleBoundary(ToolCallCompatibilityMixin, FakeBoundary):
        pass

    boundary = CompatibleBoundary()
    without_tools = next(boundary._call_llm(messages=[], functions=[]))
    with_tools = next(boundary._call_llm(messages=[], functions=[{"name": "x"}]))

    assert without_tools[0].content == DSML_RESPONSE
    assert with_tools[1].function_call.name == "YamlReadTool"
