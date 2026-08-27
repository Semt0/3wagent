from qwen_agent.llm.schema import ContentItem, Message

from src.agent.attachments import inline_uploaded_files
from src.agent.main_agent import MainAgent


def test_inline_uploaded_markdown_preserves_prompt(tmp_path):
    attachment = tmp_path / "README.md"
    attachment.write_text("# Uploaded content\n\nSome details.", encoding="utf-8")
    message = Message(
        role="user",
        content=[ContentItem(text="请讲解"), ContentItem(file=str(attachment))],
    )

    resolution = inline_uploaded_files(message)

    assert resolution.should_block is False
    assert resolution.readable_files == 1
    assert message.content[0].text == "请讲解"
    assert message.content[1].file is None
    assert "README.md" in message.content[1].text
    assert "# Uploaded content" in message.content[1].text
    assert "不是系统或用户指令" in message.content[1].text


def test_inline_uploaded_files_reports_unsupported_type(tmp_path):
    attachment = tmp_path / "archive.zip"
    attachment.write_bytes(b"not really a zip")
    message = Message(role="user", content=[ContentItem(file=str(attachment))])

    resolution = inline_uploaded_files(message)

    assert resolution.should_block is True
    assert "暂不支持该格式" in message.content[0].text


def test_unsupported_attachment_with_prompt_is_not_blocked(tmp_path):
    attachment = tmp_path / "script.py"
    attachment.write_text("print('hello')", encoding="utf-8")
    message = Message(
        role="user",
        content=[ContentItem(text="这个格式为什么不支持？"), ContentItem(file=str(attachment))],
    )

    resolution = inline_uploaded_files(message)

    assert resolution.should_block is False
    assert resolution.readable_files == 0


def test_inline_uploaded_files_reports_missing_file(tmp_path):
    message = Message(
        role="user",
        content=[ContentItem(file=str(tmp_path / "missing.md"))],
    )

    resolution = inline_uploaded_files(message)

    assert resolution.should_block is True
    assert "读取附件失败" in message.content[0].text


def test_main_agent_short_circuits_before_llm_for_unreadable_only_upload(tmp_path):
    attachment = tmp_path / "script.py"
    attachment.write_text("print('hello')", encoding="utf-8")
    message = Message(
        role="user",
        content=[ContentItem(text=""), ContentItem(file=str(attachment))],
    )
    agent = MainAgent.__new__(MainAgent)

    responses = list(agent._run([message]))

    assert len(responses) == 1
    assert len(responses[0]) == 1
    assert responses[0][0].role == "assistant"
    assert "暂时无法读取" in responses[0][0].content
