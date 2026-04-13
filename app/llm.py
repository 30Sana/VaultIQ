import logging
from groq import Groq

from app.config import GROQ_API_KEY, LLM_MODEL, SYSTEM_PROMPT

logger = logging.getLogger(__name__)

_client = None


def get_client():
    global _client
    if _client is None:
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not set. Add it to your .env file.")
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


def build_context(chunks):
    parts = []
    for i, chunk in enumerate(chunks, start=1):
        parts.append(f"[{i}] (Source: {chunk['filename']}, Page {chunk['page']})\n{chunk['text']}")
    return "\n\n".join(parts)


def answer(question: str, chunks: list) -> str:
    if not chunks:
        return "I couldn't find any relevant content in the uploaded documents to answer that."

    context = build_context(chunks)
    user_message = f"Context:\n{context}\n\nQuestion: {question}"

    try:
        response = get_client().chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.2,
            max_tokens=1024,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        raise
