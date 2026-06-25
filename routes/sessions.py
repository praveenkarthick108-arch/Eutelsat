from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from database import get_db
import models
from schemas import SessionOut, SessionListItem

router = APIRouter()


@router.get("/sessions", response_model=List[SessionListItem])
def list_sessions(db: Session = Depends(get_db)):
    return (
        db.query(models.GenerationSession)
        .order_by(models.GenerationSession.created_at.desc())
        .all()
    )


@router.get("/sessions/{session_id}", response_model=SessionOut)
def get_session(session_id: int, db: Session = Depends(get_db)):
    session = (
        db.query(models.GenerationSession)
        .filter(models.GenerationSession.id == session_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/sessions/{session_id}")
def delete_session(session_id: int, db: Session = Depends(get_db)):
    session = (
        db.query(models.GenerationSession)
        .filter(models.GenerationSession.id == session_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(session)
    db.commit()
    return {"ok": True}
