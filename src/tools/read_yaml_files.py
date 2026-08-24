from qwen_agent.tools.base import BaseTool, register_tool
import json5

from src.tools.common import resolve_project_path


@register_tool('YamlReadTool')
class YamlReadTool(BaseTool):
    name = "YamlReadTool"
    description = ("Read a YAML file and return its content. "
                   "Input a path relative to the project root, e.g. 'config/routing.yaml'. "
                   "Do NOT guess absolute paths.")
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "description": "File path relative to the project root, e.g. 'config/jurisdictions.yaml'",
                "type": "string"
            }
        },
        "required": ["file_path"]
    }

    def call(self, params: str, **kwargs) -> str:
        rel = json5.loads(params)["file_path"]
        try:
            path = resolve_project_path(rel)
        except (ValueError, OSError):
            return f"error: invalid path or path escapes project root: {rel}"
        if not path.is_file():
            return f"error: file not found: {rel}"
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"error: not a UTF-8 text file: {rel}"
