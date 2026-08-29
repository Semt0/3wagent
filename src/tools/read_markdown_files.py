from qwen_agent.tools.base import BaseTool, register_tool

from src.tools.common import get_file_path_param, parse_tool_params, resolve_project_path


@register_tool('MarkDownReadTool')
class MarkDownReadTool(BaseTool):
    name = "MarkDownReadTool"
    description = ("Read a Markdown/text file and return its content. "
                   "Call format: <tool_call>\n"
                   "{\"name\": \"MarkDownReadTool\", \"arguments\": {\"file_path\": \"config/routing.yaml\"}}\n"
                   "</tool_call>\n"
                   "file_path must be relative to the src runtime root. Do NOT guess absolute paths.")
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "description": "File path relative to the src runtime root, e.g. 'templates/report.md'",
                "type": "string"
            }
        },
        "required": ["file_path"]
    }

    def __init__(self, cfg=None):
        super().__init__(cfg)
        # Paths already read by this agent instance; small models sometimes
        # fall into degenerate re-read loops when they hesitate to conclude.
        self._seen_paths: set = set()

    def call(self, params: str, **kwargs) -> str:
        try:
            par = parse_tool_params(params)
        except Exception:
            return ('error: invalid arguments. Use a JSON object like '
                    '{"file_path": "config/routing.yaml"} (arguments itself must NOT be a quoted string).')
        try:
            rel = get_file_path_param(par)
        except KeyError:
            return 'error: missing required parameter "file_path" (relative to the src runtime root)'
        if rel in self._seen_paths:
            return ('error: you have already read this file; its full content is in the conversation '
                    'above. Do NOT read it again. If you have enough information, STOP all tool calls '
                    'now and write your final answer as plain Markdown text (no tool call).')
        self._seen_paths.add(rel)
        try:
            path = resolve_project_path(rel)
        except (ValueError, OSError):
            return f"error: invalid path or path escapes src runtime root: {rel}"
        if not path.is_file():
            return f"error: file not found: {rel}"
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"error: not a UTF-8 text file: {rel}"
