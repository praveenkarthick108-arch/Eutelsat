import os
import re
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response as FastResponse
from sqlalchemy.orm import Session

from database import get_db
import models
from ai_pipeline import automation_agent

router = APIRouter()

# Framework root — one level up from the tool, into eutelsat-sit-framework
_TOOL_ROOT = Path(__file__).parent.parent
_FRAMEWORK_ROOT = _TOOL_ROOT.parent / "eutelsat-sit-framework"

_MODULE_FOLDER = {
    "Customer Portal":           "customer-portal",
    "Contracts / CIM":           "contracts-cim",
    "CPQ / EPC":                 "cpq-epc",
    "Order Management":          "order-management",
    "Billing / Charging":        "billing-charging",
    "Inv. & Accounting":         "inv-accounting",
    "API / Integration":         "api-integration",
    "Provisioning / Activation": "api-integration",
    "ServiceNow / ITSM":         "api-integration",
}

_SCRIPT_DEST = {
    "postman":    ("api-tests/collections", ".json"),
    "playwright": ("ui-tests/tests",        ".spec.js"),
    "python":     ("e2e-tests/tests",       ".py"),
}


def _safe_name(s: str) -> str:
    return re.sub(r"[^\w\-]", "_", s)[:50]

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


@router.post("/automation/{session_id}/export")
def export_to_framework(
    session_id: int,
    script_type: Literal["postman", "playwright", "python", "all"] = Query(default="all"),
    db: Session = Depends(get_db),
):
    """Write generated script(s) directly into the eutelsat-sit-framework folder."""
    if not _FRAMEWORK_ROOT.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Framework folder not found at: {_FRAMEWORK_ROOT}. Make sure eutelsat-sit-framework exists next to eutelsat-testgen.",
        )

    sess = db.query(models.GenerationSession).filter(models.GenerationSession.id == session_id).first()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    types = ["postman", "playwright", "python"] if script_type == "all" else [script_type]
    exported = []
    skipped = []

    for stype in types:
        script = db.query(models.AutomationScript).filter(
            models.AutomationScript.session_id == session_id,
            models.AutomationScript.script_type == stype,
        ).first()

        if not script:
            skipped.append({"type": stype, "reason": "Not generated yet — generate the script first"})
            continue

        dest_dir, ext = _SCRIPT_DEST[stype]
        module_folder = _MODULE_FOLDER.get(sess.module, "api-integration")
        out_dir = _FRAMEWORK_ROOT / dest_dir / module_folder
        out_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{_safe_name(sess.feature_title)}_session{session_id}{ext}"
        filepath = out_dir / filename
        filepath.write_text(script.content, encoding="utf-8")

        rel = str(filepath.relative_to(_FRAMEWORK_ROOT))
        exported.append({"type": stype, "path": f"eutelsat-sit-framework/{rel}"})

    if not exported and skipped:
        raise HTTPException(
            status_code=400,
            detail=f"Nothing exported. {skipped[0]['reason']}",
        )

    return {
        "exported": exported,
        "skipped": skipped,
        "framework_root": str(_FRAMEWORK_ROOT),
    }
