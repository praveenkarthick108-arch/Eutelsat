from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from database import get_db
from rag import ingest as rag_ingest
from rag import retriever as rag_retriever
from ai_pipeline import client

router = APIRouter()


@router.get("/rag/status")
def rag_status(db: Session = Depends(get_db)):
    return rag_retriever.rag_status(db)


@router.post("/rag/ingest")
def rag_ingest_endpoint(force: bool = False, db: Session = Depends(get_db)):
    result = rag_ingest.ingest(db, client, force=force)
    return result
