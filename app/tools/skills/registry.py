from app.tools.skills.loader import load_template
from app.tools.skills.schemas import RuntimeSkill

SKILLS: dict[str, RuntimeSkill] = {
    "funds_analysis": RuntimeSkill(
        name="funds_analysis",
        description="Funds flow, banking compliance, AML and sanctions analysis.",
        template_path="funds_analysis.md",
    ),
    "tax_analysis": RuntimeSkill(
        name="tax_analysis",
        description="Tax analysis for cross-border policy questions.",
        template_path="tax_analysis.md",
    ),
    "commercial_analysis": RuntimeSkill(
        name="commercial_analysis",
        description="Corporate and commercial law analysis.",
        template_path="commercial_analysis.md",
    ),
    "citation_verification": RuntimeSkill(
        name="citation_verification",
        description="Evidence and citation verification.",
        template_path="citation_verification.md",
    ),
}


def get_runtime_skill(name: str) -> RuntimeSkill:
    return SKILLS[name]


def get_skill_template(name: str) -> str:
    skill = get_runtime_skill(name)
    return load_template(skill.template_path)

