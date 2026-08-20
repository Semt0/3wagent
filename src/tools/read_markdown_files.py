from qwen_agent.tools.base import BaseTool, register_tool
import json5

@register_tool('MarkDownReadTool')
class MarkDownReadTool(BaseTool):
    name = "MarkDownReadTool"
    description = "MarkDown File Reading Tool, input file absolute address, and return file content."
    parameters = {
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