from qwen_agent.tools.base import BaseTool, register_tool
from pathlib import Path
import json5


@register_tool("WriteResult")
class WriteResult(BaseTool):
    name = "WriteResult"
    description = "Writing Result Tool, input file absolute address and file contents, output writed file."
    parameters = {
        "type" : "object",
        "properties" : {
            "absolute_address" :{
                "description" :"Absolute Address of the target file",
                "type" : "string"
            },
            "file_content" :{
                "description" :"File Exact Content As String",
                "type" : "string"
            }
        },
        "required": ["absolute_address", "file_content"]
    }

    def call(self, params: str, **kwargs):
        par = json5.loads(params)
        addr = Path(par["absolute_address"])
        addr.parent.mkdir(parents=True, exist_ok=True)
        addr.write_text(par["file_content"])