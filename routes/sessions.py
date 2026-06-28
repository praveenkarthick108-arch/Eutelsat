from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any

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


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Aggregate statistics for the Dashboard view."""
    sessions = db.query(models.GenerationSession).all()
    test_cases = db.query(models.TestCase).all()

    tc_by_type: Dict[str, int] = {}
    tc_by_module: Dict[str, int] = {}
    tc_by_priority: Dict[str, int] = {"High": 0, "Medium": 0, "Low": 0}
    auto_count = 0
    confidence_sum = 0.0

    for tc in test_cases:
        t = tc.type or "Unknown"
        tc_by_type[t] = tc_by_type.get(t, 0) + 1
        if tc.automation_candidate:
            auto_count += 1
        confidence_sum += float(tc.confidence_score or 0.82)
        p = tc.priority or "Medium"
        if p in tc_by_priority:
            tc_by_priority[p] += 1

    for s in sessions:
        m = s.module or "Unknown"
        tc_by_module[m] = tc_by_module.get(m, 0) + s.tc_count

    total_tc = len(test_cases)
    total_sessions = len(sessions)

    recent = sorted(sessions, key=lambda x: x.created_at, reverse=True)[:10]

    return {
        "total_sessions": total_sessions,
        "total_test_cases": total_tc,
        "automation_rate": round(auto_count / total_tc * 100) if total_tc else 0,
        "avg_confidence": round(confidence_sum / total_tc * 100) if total_tc else 0,
        "tc_by_type": tc_by_type,
        "tc_by_module": tc_by_module,
        "tc_by_priority": tc_by_priority,
        "recent_sessions": [
            {
                "id": s.id,
                "feature_title": s.feature_title[:55],
                "module": s.module,
                "test_type": s.test_type,
                "tc_count": s.tc_count,
                "tester_name": s.tester_name,
                "created_at": s.created_at.isoformat(),
            }
            for s in recent
        ],
    }
