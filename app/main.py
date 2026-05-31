from fastapi import FastAPI, File, Form, UploadFile

from app.graph.policy_graph import run_policy_workflow
from app.intake.document_intake import extract_upload_text

app = FastAPI(title="3wagent", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze")
async def analyze(question: str = Form(...), file: UploadFile | None = File(None)) -> dict[str, str]:
    file_text = await extract_upload_text(file) if file else None
    final_answer = run_policy_workflow(question=question, file_text=file_text)
    return {"answer": final_answer}

