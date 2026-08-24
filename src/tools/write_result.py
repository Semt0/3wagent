from qwen_agent.tools.base import BaseTool, register_tool
import json5

from src.tools.common import resolve_project_path


@register_tool("WriteResult")
class WriteResult(BaseTool):
    name = "WriteResult"
    description = ("Write text content to a file (creating parent directories as needed). "
                   "Input a path relative to the project root, e.g. 'workspace/sub_agents/routing_agent_result.md'. "
                   "Do NOT guess absolute paths.")
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "description": "File path relative to the project root",
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
        par = json5.loads(params)
        rel = par["file_path"]
        try:
            path = resolve_project_path(rel)
        except (ValueError, OSError):
            return f"error: invalid path or path escapes project root: {rel}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(par["file_content"], encoding="utf-8")
        return f"ok: wrote {len(par['file_content'])} chars to {rel}"
