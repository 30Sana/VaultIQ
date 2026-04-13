from app.ingest import get_embedder, get_collection
from app.config import TOP_K


def retrieve(query: str, top_k: int = TOP_K):
    embedding = get_embedder().encode([query], show_progress_bar=False).tolist()

    results = get_collection().query(
        query_embeddings=embedding,
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for text, meta, dist in zip(docs, metas, distances):
        chunks.append({
            "text": text,
            "filename": meta.get("filename", "unknown"),
            "page": meta.get("page", 1),
            "score": round(1 - dist, 4),  # cosine similarity
        })

    return chunks
