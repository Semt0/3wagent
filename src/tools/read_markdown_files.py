from typing import ClassVar

import json5
from qwen_agent.tools.base import BaseTool, register_tool


@register_tool('MarkDownReadTool')
class MarkDownReadTool(BaseTool):
    name = "MarkDownReadTool"
    description = "MarkDown File Reading Tool, input markdown file absolute address, and return markdown file content."
    parameters: ClassVar[dict] = {
        "type" : "object",
        "properties" : {
            "absolute_address" :{
                "description" :"Absolute Address of the target markdown file",
                "type" : "string"
            }
        },
        "required": ["absolute_address"]
    }

    def call(self, params: str, **kwargs) -> str:
        absolute_address = json5.loads(params)["absolute_address"]
        with open(absolute_address, "r", encoding="utf-8") as f:
            content = f.read()
        return content
