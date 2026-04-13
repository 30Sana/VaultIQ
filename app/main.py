import logging
import shutil
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import UPLOAD_DIR, ALLOWED_EXTENSIONS
from app.ingest import ingest_file, delete_document, list_documents
from app.retriever import retrieve
from app.llm import answer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="VaultIQ", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuestionRequest(BaseModel):
    question: str
    top_k: int = 5


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type '{ext}' not supported. Use PDF, DOCX, or TXT.")

    dest = UPLOAD_DIR / file.filename
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        num_chunks = ingest_file(dest)
    except Exception as e:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")

    return {"filename": file.filename, "chunks_stored": num_chunks}


@app.post("/ask")
def ask_question(body: QuestionRequest):
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    chunks = retrieve(body.question, top_k=body.top_k)

    try:
        response = answer(body.question, chunks)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "answer": response,
        "sources": [
            {"filename": c["filename"], "page": c["page"], "score": c["score"]}
            for c in chunks
        ],
    }


@app.get("/documents")
def get_documents():
    return list_documents()


@app.delete("/documents/{filename}")
def remove_document(filename: str):
    deleted = delete_document(filename)
    if deleted == 0:
        raise HTTPException(status_code=404, detail=f"Document '{filename}' not found.")
    return {"deleted": filename, "chunks_removed": deleted}
