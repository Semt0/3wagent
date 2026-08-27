"""Message-level attachment entry point for the agent layer.

Keeps the original ``inline_uploaded_files(message)`` contract but routes all
parsing through the unified ingestion layer (``src.attachments``). File
content is inlined when small; large files are summarized and read on demand
via AttachmentReadTool.
"""

from dataclasses import dataclass
from pathlib import Path

from qwen_agent.llm.schema import ContentItem, Message

from src.attachments import registry
from src.attachments.service import ingest_file
from src.config.attachments import ATTACHMENT_SETTINGS


@dataclass(frozen=True)
class AttachmentResolution:
    had_uploads: bool
    readable_files: int
    has_user_text: bool

    @property
    def should_block(self) -> bool:
        """Whether the request has neither an instruction nor a readable attachment."""
        return self.had_uploads and self.readable_files == 0 and not self.has_user_text


def supported_formats_hint() -> str:
    return '、'.join(registry.supported_suffixes())


def inline_uploaded_files(message: Message) -> AttachmentResolution:
    """Replace uploaded file items with content the text-only LLM can read."""
    if not isinstance(message.content, list):
        return AttachmentResolution(
            had_uploads=False,
            readable_files=0,
            has_user_text=bool(message.content.strip()),
        )

    resolved_content: list[ContentItem] = []
    had_uploads = False
    readable_files = 0
    inline_budget = ATTACHMENT_SETTINGS.inline_max_chars_total
    has_user_text = any(item.text is not None and item.text.strip() for item in message.content)

    for item in message.content:
        if not item.file:
            resolved_content.append(item)
            continue

        had_uploads = True
        result = ingest_file(Path(item.file), inline_budget=inline_budget)
        if result.readable:
            readable_files += 1
            inline_budget -= len(result.inline_text)
        resolved_content.append(ContentItem(text=result.inline_text))

    message.content = resolved_content
    return AttachmentResolution(
        had_uploads=had_uploads,
        readable_files=readable_files,
        has_user_text=has_user_text,
    )
