import hashlib
import logging
from pathlib import Path

import chromadb
import fitz  # PyMuPDF
from docx import Document as DocxDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

from app.config import (
    CHROMA_PERSIST_DIR,
    CHROMA_COLLECTION,
    EMBEDDING_MODEL,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    UPLOAD_DIR,
)

logger = logging.getLogger(__name__)

_embedder = None
_collection = None


def get_embedder():
    global _embedder
    if _embedder is None:
        logger.info("Loading embedding model...")
        _embedder = SentenceTransformer(EMBEDDING_MODEL)
    return _embedder


def get_collection():
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=str(CHROMA_PERSIST_DIR))
        _collection = client.get_or_create_collection(
            name=CHROMA_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


# --- parsers ---

def _parse_pdf(path: Path):
    pages = []
    with fitz.open(str(path)) as doc:
        for i, page in enumerate(doc, start=1):
            text = page.get_text("text", sort=True).strip()
            if text:
                pages.append({"text": text, "page": i})
    return pages


def _parse_docx(path: Path):
    doc = DocxDocument(str(path))
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return [{"text": text, "page": 1}]


def _parse_txt(path: Path):
    return [{"text": path.read_text(encoding="utf-8", errors="replace").strip(), "page": 1}]


def parse_document(path: Path):
    ext = path.suffix.lower()
    if ext == ".pdf":
        return _parse_pdf(path)
    elif ext == ".docx":
        return _parse_docx(path)
    elif ext == ".txt":
        return _parse_txt(path)
    raise ValueError(f"Unsupported file type: {ext}")


# --- chunking ---

def chunk_pages(pages, filename):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = []
    for page in pages:
        for i, split in enumerate(splitter.split_text(page["text"])):
            chunks.append({
                "text": split,
                "filename": filename,
                "page": page["page"],
                "chunk_index": i,
            })
    return chunks


def _make_id(filename, page, chunk_index):
    return hashlib.md5(f"{filename}::p{page}::c{chunk_index}".encode()).hexdigest()


# --- main entry points ---

def ingest_file(file_path: Path) -> int:
    filename = file_path.name
    pages = parse_document(file_path)
    if not pages:
        return 0

    chunks = chunk_pages(pages, filename)
    if not chunks:
        return 0

    texts = [c["text"] for c in chunks]
    embeddings = get_embedder().encode(texts, show_progress_bar=False).tolist()

    ids = [_make_id(c["filename"], c["page"], c["chunk_index"]) for c in chunks]
    metadatas = [{"filename": c["filename"], "page": c["page"], "chunk_index": c["chunk_index"]} for c in chunks]

    get_collection().upsert(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
    logger.info("Stored %d chunks for %s", len(chunks), filename)
    return len(chunks)


def delete_document(filename: str) -> int:
    collection = get_collection()
    results = collection.get(where={"filename": filename})
    ids = results.get("ids", [])
    if ids:
        collection.delete(ids=ids)

    file_path = UPLOAD_DIR / filename
    if file_path.exists():
        file_path.unlink()

    return len(ids)


def list_documents():
    results = get_collection().get(include=["metadatas"])
    metadatas = results.get("metadatas") or []

    docs = {}
    for m in metadatas:
        fname = m["filename"]
        if fname not in docs:
            docs[fname] = {"filename": fname, "chunks": 0, "pages": set()}
        docs[fname]["chunks"] += 1
        docs[fname]["pages"].add(m["page"])

    return [
        {"filename": v["filename"], "chunk_count": v["chunks"], "page_count": len(v["pages"])}
        for v in docs.values()
    ]
