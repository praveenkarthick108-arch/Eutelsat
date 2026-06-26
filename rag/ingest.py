"""Document ingestion: PDF + TXT → chunk → embed → store in SQLite."""
import os
import json
import re
from sqlalchemy.orm import Session

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
CHUNK_SIZE = 600
CHUNK_OVERLAP = 80
EMBED_MODEL = "nvidia/nv-embedqa-e5-v5"

DOCS = [
    "CxP_Eutelsat_2026.pdf",
    "prodapt_lotb_context.txt",
]


def _chunk(text: str):
    """Generator: yield chunks one at a time to avoid holding all in memory."""
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        if end < len(text):
            for sep in ["\n\n", "\n", ". ", " "]:
                pos = text.rfind(sep, start + CHUNK_SIZE // 2, end)
                if pos != -1:
                    end = pos + len(sep)
                    break
        chunk = text[start:end].strip()
        if len(chunk) > 40:
            yield chunk
        start = end - CHUNK_OVERLAP


def _embed(texts: list, client) -> list:
    try:
        resp = client.embeddings.create(
            input=texts,
            model=EMBED_MODEL,
            encoding_format="float",
            extra_body={"input_type": "passage", "truncate": "END"},
        )
        return [item.embedding for item in resp.data]
    except Exception as e:
        print(f"[RAG Embed] Error: {e}")
        return [[] for _ in texts]


def _ingest_one(source_name: str, db: Session, client, force: bool = False) -> dict:
    import models

    path = os.path.join(DOCS_DIR, source_name)
    if not os.path.exists(path):
        print(f"[RAG] Skipping {source_name} — not found")
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
        db.commit()

    print(f"[RAG] Ingesting {source_name}...")
    ext = os.path.splitext(source_name)[1].lower()

    count = 0
    BATCH = 4  # smaller batches to keep memory low

    if ext == ".pdf":
        import pypdf
        with open(path, "rb") as f:
            reader = pypdf.PdfReader(f)
            page_count = len(reader.pages)
            print(f"[RAG] PDF has {page_count} pages")
            batch, idxs = [], []
            for pg_num, page in enumerate(reader.pages):
                page_text = page.extract_text() or ""
                if not page_text.strip():
                    continue
                for chunk in _chunk(page_text):
                    batch.append(chunk)
                    idxs.append(count)
                    if len(batch) >= BATCH:
                        embs = _embed(batch, client)
                        for i, (ch, emb) in enumerate(zip(batch, embs)):
                            db.add(models.DocumentChunk(
                                source=source_name, chunk_index=idxs[i],
                                text=ch, embedding=json.dumps(emb),
                            ))
                        count += len(batch)
                        db.flush()
                        batch, idxs = [], []
                if (pg_num + 1) % 5 == 0:
                    db.commit()
                    print(f"[RAG] {source_name}: page {pg_num+1}/{page_count}, {count} chunks so far")
            # flush remainder
            if batch:
                embs = _embed(batch, client)
                for i, (ch, emb) in enumerate(zip(batch, embs)):
                    db.add(models.DocumentChunk(
                        source=source_name, chunk_index=idxs[i],
                        text=ch, embedding=json.dumps(emb),
                    ))
                count += len(batch)

    else:  # .txt / .md
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        batch, idxs = [], []
        for chunk in _chunk(text):
            batch.append(chunk)
            idxs.append(count)
            if len(batch) >= BATCH:
                embs = _embed(batch, client)
                for i, (ch, emb) in enumerate(zip(batch, embs)):
                    db.add(models.DocumentChunk(
                        source=source_name, chunk_index=idxs[i],
                        text=ch, embedding=json.dumps(emb),
                    ))
                count += len(batch)
                db.flush()
                batch, idxs = [], []
                if count % 40 == 0:
                    db.commit()
        if batch:
            embs = _embed(batch, client)
            for i, (ch, emb) in enumerate(zip(batch, embs)):
                db.add(models.DocumentChunk(
                    source=source_name, chunk_index=idxs[i],
                    text=ch, embedding=json.dumps(emb),
                ))
            count += len(batch)

    db.commit()
    print(f"[RAG] {source_name}: complete — {count} chunks stored")
    return {"status": "ingested", "chunks": count, "source": source_name}


def ingest(db: Session, client, force: bool = False) -> dict:
    """Ingest all documents. Returns summary."""
    total = 0
    results = []
    for doc in DOCS:
        r = _ingest_one(doc, db, client, force=force)
        results.append(r)
        total += r.get("chunks", 0)

    all_already = all(r["status"] == "already_ingested" for r in results)
    status = "already_ingested" if all_already else "ingested"
    return {"status": status, "chunks": total, "source": ", ".join(DOCS), "details": results}
