from pydantic import BaseModel


class RuntimeSkill(BaseModel):
    name: str
    description: str
    template_path: str

