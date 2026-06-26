"""Document ingestion: PDF + TXT → chunk → embed → store in SQLite."""
import os
import json
import re
from sqlalchemy.orm import Session

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
CHUNK_SIZE = 700
CHUNK_OVERLAP = 120
EMBED_MODEL = "nvidia/nv-embedqa-e5-v5"

# All documents to ingest
DOCS = [
    "CxP_Eutelsat_2026.pdf",
    "prodapt_lotb_context.txt",
]


def _extract_pdf(pdf_path: str) -> str:
    import pypdf
    text_parts = []
    with open(pdf_path, "rb") as f:
        reader = pypdf.PdfReader(f)
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    return "\n".join(text_parts)


def _extract_txt(txt_path: str) -> str:
    with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def extract_text(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return _extract_pdf(path)
    if ext in (".txt", ".md"):
        return _extract_txt(path)
    return ""


def chunk_text(text: str) -> list[str]:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    chunks, start = [], 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        if end < len(text):
            for sep in ["\n\n", "\n", ". ", " "]:
                pos = text.rfind(sep, start + CHUNK_SIZE // 2, end)
                if pos != -1:
                    end = pos + len(sep)
                    break
        chunk = text[start:end].strip()
        if len(chunk) > 50:
            chunks.append(chunk)
        start = end - CHUNK_OVERLAP
    return chunks


def _get_embedding(texts: list[str], client) -> list[list[float]]:
    try:
        response = client.embeddings.create(
            input=texts,
            model=EMBED_MODEL,
            encoding_format="float",
            extra_body={"input_type": "passage", "truncate": "END"},
        )
        return [item.embedding for item in response.data]
    except Exception as e:
        print(f"[RAG Embed] Error: {e}")
        return [[] for _ in texts]


def _ingest_one(source_name: str, db: Session, client, force: bool = False) -> dict:
    """Ingest a single document. Returns status dict."""
    import models

    path = os.path.join(DOCS_DIR, source_name)

    if not os.path.exists(path):
        print(f"[RAG] Skipping {source_name} — file not found")
        return {"status": "not_found", "chunks": 0, "source": source_name}

    if not force:
        existing = db.query(models.DocumentChunk).filter(
            models.DocumentChunk.source == source_name
        ).count()
        if existing > 0:
            print(f"[RAG] Already ingested: {existing} chunks from {source_name}")
            return {"status": "already_ingested", "chunks": existing, "source": source_name}

    if force:
        db.query(models.DocumentChunk).filter(
            models.DocumentChunk.source == source_name
        ).delete()

    print(f"[RAG] Ingesting {source_name}...")
    text = extract_text(path)
    if not text.strip():
        return {"status": "empty", "chunks": 0, "source": source_name}

    chunks = chunk_text(text)
    print(f"[RAG] {len(chunks)} chunks from {source_name}, embedding...")

    BATCH = 8
    count = 0
    for i in range(0, len(chunks), BATCH):
        batch = chunks[i: i + BATCH]
        embeddings = _get_embedding(batch, client)
        for j, (chunk, emb) in enumerate(zip(batch, embeddings)):
            db.add(models.DocumentChunk(
                source=source_name,
                chunk_index=i + j,
                text=chunk,
                embedding=json.dumps(emb),
            ))
            count += 1
        if i % 40 == 0:
            print(f"[RAG] {source_name}: {min(i + BATCH, len(chunks))}/{len(chunks)} chunks embedded")
        db.flush()

    db.commit()
    print(f"[RAG] {source_name}: {count} chunks stored")
    return {"status": "ingested", "chunks": count, "source": source_name}


def ingest(db: Session, client, force: bool = False) -> dict:
    """Ingest all documents in DOCS list. Returns summary."""
    results = []
    total_chunks = 0
    for doc in DOCS:
        r = _ingest_one(doc, db, client, force=force)
        results.append(r)
        total_chunks += r.get("chunks", 0)

    statuses = [r["status"] for r in results]
    if all(s == "already_ingested" for s in statuses):
        return {"status": "already_ingested", "chunks": total_chunks, "source": ", ".join(DOCS)}

    return {"status": "ingested", "chunks": total_chunks, "source": ", ".join(DOCS), "details": results}
