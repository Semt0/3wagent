from pathlib import Path

TEMPLATE_DIR = Path(__file__).parent / "templates"


def load_template(filename: str) -> str:
    path = TEMPLATE_DIR / filename
    return path.read_text(encoding="utf-8")

