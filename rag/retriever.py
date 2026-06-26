"""Retrieval: embed query → cosine similarity → return top-k context."""
import json
import math
import re
from sqlalchemy.orm import Session

EMBED_MODEL = "nvidia/nv-embedqa-e5-v5"
TOP_K = 4
MIN_SCORE = 0.25


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(x * x for x in b))
    return dot / mag if mag else 0.0


def _keyword_score(query: str, text: str) -> float:
    """Simple word-overlap fallback when embeddings are unavailable."""
    qw = set(re.findall(r"\w+", query.lower()))
    tw = set(re.findall(r"\w+", text.lower()))
    if not qw:
        return 0.0
    return len(qw & tw) / len(qw)


def _embed_query(query: str, client) -> list[float]:
    try:
        response = client.embeddings.create(
            input=[query],
            model=EMBED_MODEL,
            encoding_format="float",
            extra_body={"input_type": "query", "truncate": "END"},
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"[RAG Retrieve] Embed error: {e}")
        return []


def retrieve(
    query: str,
    db: Session,
    client,
    top_k: int = TOP_K,
    min_score: float = MIN_SCORE,
) -> str:
    """
    Retrieve the most relevant document chunks for the given query.
    Returns a formatted context string, or empty string if nothing found.
    """
    import models

    chunks = db.query(models.DocumentChunk).all()
    if not chunks:
        return ""

    query_emb = _embed_query(query, client)
    scored = []

    for c in chunks:
        emb = json.loads(c.embedding or "[]")
        if query_emb and emb:
            score = _cosine(query_emb, emb)
        else:
            score = _keyword_score(query, c.text)
        scored.append((score, c.text))

    scored.sort(key=lambda x: -x[0])
    top = [text for score, text in scored[:top_k] if score >= min_score]

    if not top:
        return ""

    return "\n\n---\n\n".join(top)


def rag_status(db: Session) -> dict:
    """Return current RAG index status."""
    import models

    total = db.query(models.DocumentChunk).count()
    if total == 0:
        return {"ready": False, "chunks": 0, "source": None}

    first = db.query(models.DocumentChunk).first()
    return {"ready": True, "chunks": total, "source": first.source if first else None}
