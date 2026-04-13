import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads")))
CHROMA_PERSIST_DIR = Path(os.getenv("CHROMA_PERSIST_DIR", str(BASE_DIR / "chroma_db")))

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 100
TOP_K = 5

CHROMA_COLLECTION = "vaultiq_docs"
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}

SYSTEM_PROMPT = """You are a helpful assistant that answers questions based on the provided document context.
Answer using ONLY the provided context. If the answer isn't in the context, say so clearly.
Always cite your sources at the end in the format: [Source: filename, Page X]"""
