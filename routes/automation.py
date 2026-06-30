from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response as FastResponse
from sqlalchemy.orm import Session

from database import get_db
import models
from ai_pipeline import automation_agent

router = APIRouter()

_CFG = {
    "postman":    {"ext": "json", "mime": "application/json",       "label": "Postman Collection"},
    "playwright": {"ext": "js",   "mime": "text/javascript",         "label": "Playwright Tests"},
    "python":     {"ext": "py",   "mime": "text/plain; charset=utf-8", "label": "Python pytest"},
}


@router.post("/automation/{session_id}")
def generate_script(
    session_id: int,
    script_type: Literal["postman", "playwright", "python"] = Query(default="postman"),
    db: Session = Depends(get_db),
):
    sess = db.query(models.GenerationSession).filter(models.GenerationSession.id == session_id).first()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    # Return cached script if available
    cached = db.query(models.AutomationScript).filter(
        models.AutomationScript.session_id == session_id,
        models.AutomationScript.script_type == script_type,
    ).first()
    if cached:
        return {"script_type": script_type, "content": cached.content, "cached": True}

    tc_list = [
        {
            "tc_id":           tc.tc_id,
            "description":     tc.description,
            "steps":           tc.steps or "",
            "expected_result": tc.expected_result or "",
            "priority":        tc.priority,
            "type":            tc.type,
            "automation_candidate": bool(tc.automation_candidate),
            "automation_notes": tc.automation_notes or "",
        }
        for tc in sess.test_cases
    ]
    if not tc_list:
        raise HTTPException(status_code=400, detail="No test cases found in this session")

    try:
        content = automation_agent(
            feature_title=sess.feature_title,
            module=sess.module,
            system=sess.system or "",
            test_cases=tc_list,
            script_type=script_type,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Script generation failed: {exc}")

    script = models.AutomationScript(
        session_id=session_id,
        script_type=script_type,
        content=content,
    )
    db.add(script)
    db.commit()

    return {"script_type": script_type, "content": content, "cached": False}


@router.delete("/automation/{session_id}")
def clear_cached_script(
    session_id: int,
    script_type: Literal["postman", "playwright", "python"] = Query(default="postman"),
    db: Session = Depends(get_db),
):
    """Delete a cached script so next POST re-generates it."""
    deleted = db.query(models.AutomationScript).filter(
        models.AutomationScript.session_id == session_id,
        models.AutomationScript.script_type == script_type,
    ).delete()
    db.commit()
    return {"deleted": deleted}


@router.get("/automation/{session_id}/download")
def download_script(
    session_id: int,
    script_type: Literal["postman", "playwright", "python"] = Query(default="postman"),
    db: Session = Depends(get_db),
):
    sess = db.query(models.GenerationSession).filter(models.GenerationSession.id == session_id).first()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    script = db.query(models.AutomationScript).filter(
        models.AutomationScript.session_id == session_id,
        models.AutomationScript.script_type == script_type,
    ).first()
    if not script:
        raise HTTPException(status_code=404, detail="Script not generated yet — call POST /api/automation/{id} first")

    cfg = _CFG[script_type]
    safe = sess.feature_title[:40].replace(" ", "_").replace("/", "-")
    filename = f"Eutelsat_{safe}_{script_type}.{cfg['ext']}"

    return FastResponse(
        content=script.content.encode("utf-8"),
        media_type=cfg["mime"],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
