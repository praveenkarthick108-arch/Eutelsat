import threading
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db, SessionLocal
from rag import ingest as rag_ingest
from rag import retriever as rag_retriever
from ai_pipeline import client

router = APIRouter()

_ingest_status = {"running": False, "last": None}


def _make_client():
    """Create a fresh OpenAI client for use in background threads."""
    import os, httpx
    from openai import OpenAI
    return OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=os.getenv("NVIDIA_API_KEY"),
        http_client=httpx.Client(verify=False),
    )


def _run_ingest_bg(force: bool):
    _ingest_status["running"] = True
    db = SessionLocal()
    bg_client = _make_client()
    try:
        result = rag_ingest.ingest(db, bg_client, force=force)
        _ingest_status["last"] = result
        print(f"[RAG] Ingest complete: {result}")
    except Exception as e:
        _ingest_status["last"] = {"status": "error", "error": str(e)}
        print(f"[RAG] Ingest error: {e}")
    finally:
        _ingest_status["running"] = False
        db.close()


@router.get("/rag/status")
def rag_status(db: Session = Depends(get_db)):
    status = rag_retriever.rag_status(db)
    status["ingest_running"] = _ingest_status["running"]
    return status


@router.post("/rag/ingest")
def rag_ingest_endpoint(force: bool = False):
    if _ingest_status["running"]:
        return {"status": "already_running", "message": "Ingest is already in progress"}
    t = threading.Thread(target=_run_ingest_bg, args=(force,), daemon=True)
    t.start()
    return {"status": "started", "message": "Ingest started in background — poll /api/rag/status to track progress"}
