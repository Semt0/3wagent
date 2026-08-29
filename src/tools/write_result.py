from qwen_agent.tools.base import BaseTool, register_tool

from src.tools.common import get_file_path_param, parse_tool_params, resolve_project_path


def _salvage_params(params) -> dict | None:
    """Lenient last-resort parse for malformed WriteResult arguments.

    Small models often double-encode the arguments and then break an escape
    inside the large file_content, so strict JSON parsing fails. Inspired by
    codex's lenient apply_patch parser: extract file_path with a regex and
    take the raw remainder after "file_content": as the content, forgiving
    common escape sequences.
    """
    import re

    if not isinstance(params, str):
        return None
    text = params.strip()
    # One level of double-encoding: the payload itself is a quoted string.
    if text.startswith('"') and text.endswith('"'):
        try:
            import json5
            text = json5.loads(text)
        except Exception:
            text = text[1:-1]
    path_match = re.search(r'"file_path"\s*:\s*"([^"]+)"', text)
    content_match = re.search(r'"file_content"\s*:\s*"', text)
    if not (path_match and content_match):
        return None
    content = text[content_match.end():]
    # Strip the trailing JSON closers, then forgive the common escapes.
    content = content.rstrip()
    for trailer in ('"}', '"', '}'):
        if content.endswith(trailer):
            content = content[: -len(trailer)]
            break
    content = content.replace('\\"', '"').replace('\\n', '\n').replace('\\\\', '\\')
    if not content.strip():
        return None
    return {'file_path': path_match.group(1), 'file_content': content}


@register_tool("WriteResult")
class WriteResult(BaseTool):
    name = "WriteResult"
    description = ("Write text content to a file (creating parent directories as needed). "
                   "Call format: <tool_call>\n"
                   "{\"name\": \"WriteResult\", \"arguments\": {\"file_path\": \"workspace/sub_agents/xxx_result.md\", "
                   "\"file_content\": \"...\"}}\n"
                   "</tool_call>\n"
                   "file_path must be relative to the src runtime root. Do NOT guess absolute paths. "
                   "arguments must be a JSON object, NOT a quoted string.")
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "description": "File path relative to the src runtime root",
                "type": "string"
            },
            "file_content": {
                "description": "File exact content as string",
                "type": "string"
            }
        },
        "required": ["file_path", "file_content"]
    }

    def call(self, params: str, **kwargs) -> str:
        try:
            par = parse_tool_params(params)
        except Exception:
            par = _salvage_params(params)
            if par is None:
                return ('error: invalid arguments. Use a JSON object like '
                        '{"file_path": "workspace/sub_agents/xxx_result.md", "file_content": "..."} '
                        '(arguments itself must NOT be a quoted string).')
        try:
            rel = get_file_path_param(par)
        except KeyError:
            return 'error: missing required parameter "file_path" (relative to the src runtime root)'
        content = par.get("file_content")
        if not isinstance(content, str):
            return 'error: missing required parameter "file_content" (a string)'
        try:
            path = resolve_project_path(rel)
        except (ValueError, OSError):
            return f"error: invalid path or path escapes src runtime root: {rel}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"ok: wrote {len(content)} chars to {rel}"
