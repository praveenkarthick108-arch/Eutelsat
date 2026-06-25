from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
import models
from schemas import FollowupRequest, FollowupResponse, TestCaseOut
from ai_pipeline import followup_agent

router = APIRouter()


@router.post("/sessions/{session_id}/followup", response_model=FollowupResponse)
def followup_query(session_id: int, req: FollowupRequest, db: Session = Depends(get_db)):
    session = (
        db.query(models.GenerationSession)
        .filter(models.GenerationSession.id == session_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    existing = db.query(models.TestCase).filter(models.TestCase.session_id == session_id).all()
    existing_dicts = [
        {
            "tc_id": tc.tc_id,
            "description": tc.description,
            "steps": tc.steps,
            "expected_result": tc.expected_result,
            "priority": tc.priority,
        }
        for tc in existing
    ]

    result = followup_agent(
        query=req.query,
        feature_title=session.feature_title,
        module=session.module,
        test_type=session.test_type,
        existing_cases=existing_dicts,
    )

    # Persist new test cases if generated
    new_tc_out = []
    if result.get("type") == "new_cases" and result.get("new_cases"):
        current_count = len(existing)
        for i, tc in enumerate(result["new_cases"]):
            tc_obj = models.TestCase(
                session_id=session_id,
                tc_id=f"TC-{str(current_count + i + 1).zfill(3)}",
                description=tc.get("description", ""),
                type=session.test_type,
                priority=tc.get("priority", "Medium"),
                steps=tc.get("steps", ""),
                expected_result=tc.get("expected_result", ""),
                confidence_score=tc.get("confidence_score", 0.80),
                hallucination_risk=tc.get("hallucination_risk", "Low"),
            )
            db.add(tc_obj)
            db.flush()
            new_tc_out.append(TestCaseOut.model_validate(tc_obj))

        session.tc_count = current_count + len(result["new_cases"])
        db.commit()

    return FollowupResponse(
        type=result.get("type", "answer"),
        message=result.get("message", ""),
        new_cases=new_tc_out,
    )
