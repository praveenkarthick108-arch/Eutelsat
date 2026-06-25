from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
import models
from schemas import TestCaseUpdate, TestCaseOut

router = APIRouter()


@router.put("/testcases/{tc_id}", response_model=TestCaseOut)
def update_test_case(
    tc_id: int, update: TestCaseUpdate, db: Session = Depends(get_db)
):
    tc = db.query(models.TestCase).filter(models.TestCase.id == tc_id).first()
    if not tc:
        raise HTTPException(status_code=404, detail="Test case not found")

    if update.description is not None:
        tc.description = update.description
    if update.priority is not None:
        tc.priority = update.priority
    if update.steps is not None:
        tc.steps = update.steps
    if update.expected_result is not None:
        tc.expected_result = update.expected_result

    tc.is_edited = True
    db.commit()
    db.refresh(tc)
    return tc
