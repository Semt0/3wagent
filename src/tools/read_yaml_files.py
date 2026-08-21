from qwen_agent.tools.base import BaseTool, register_tool
import yaml
import json5

@register_tool('YamlReadTool')
class YamlReadTool(BaseTool):
    name = "YamlReadTool"
    description = "Yaml File Reading Tool, input yaml file absolute address, and return yaml file content."
    parameters = {
        "type" : "object",
        "properties" : {
            "absolute_address" :{
                "description" :"Absolute Address of the target yaml file",
                "type" : "string"
            }
        },
        "required": ["absolute_address"]
    }

    def call(self, params: str, **kwargs) -> str:
        absolute_address = json5.loads(params)["absolute_address"]
        with open(absolute_address, "r", encoding="utf-8") as f:
            content = yaml.safe_load(f)
        return content