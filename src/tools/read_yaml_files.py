from qwen_agent.tools.base import BaseTool, register_tool

from src.tools.common import get_file_path_param, parse_tool_params, resolve_project_path


@register_tool('YamlReadTool')
class YamlReadTool(BaseTool):
    name = "YamlReadTool"
    description = ("Read a YAML file and return its content. "
                   "Call format: <tool_call>\n"
                   "{\"name\": \"YamlReadTool\", \"arguments\": {\"file_path\": \"config/routing.yaml\"}}\n"
                   "</tool_call>\n"
                   "file_path must be relative to the src runtime root. Do NOT guess absolute paths.")
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "description": "File path relative to the src runtime root, e.g. 'config/jurisdictions.yaml'",
                "type": "string"
            }
        },
        "required": ["file_path"]
    }

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
