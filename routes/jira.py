from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
import models
from schemas import JiraConfigIn, JiraConfigOut, JiraImportResponse, JiraImportPreview

router = APIRouter()


@router.get("/jira/config", response_model=JiraConfigOut)
def get_jira_config(db: Session = Depends(get_db)):
    cfg = db.query(models.JiraConfig).first()
    if not cfg:
        return JiraConfigOut(jira_url="", project_key="", user_email="", configured=False)
    return JiraConfigOut(
        jira_url=cfg.jira_url,
        project_key=cfg.project_key,
        user_email=cfg.user_email,
        configured=bool(cfg.jira_url and cfg.project_key and cfg.api_token),
    )


@router.post("/jira/config", response_model=JiraConfigOut)
def save_jira_config(body: JiraConfigIn, db: Session = Depends(get_db)):
    cfg = db.query(models.JiraConfig).first()
    if cfg:
        cfg.jira_url = body.jira_url
        cfg.project_key = body.project_key
        cfg.api_token = body.api_token
        cfg.user_email = body.user_email
        cfg.updated_at = datetime.utcnow()
    else:
        cfg = models.JiraConfig(
            jira_url=body.jira_url,
            project_key=body.project_key,
            api_token=body.api_token,
            user_email=body.user_email,
        )
        db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return JiraConfigOut(
        jira_url=cfg.jira_url,
        project_key=cfg.project_key,
        user_email=cfg.user_email,
        configured=bool(cfg.jira_url and cfg.project_key and cfg.api_token),
    )


@router.post("/jira/import/{session_id}", response_model=JiraImportResponse)
def import_to_jira(session_id: int, db: Session = Depends(get_db)):
    cfg = db.query(models.JiraConfig).first()
    configured = bool(cfg and cfg.jira_url and cfg.project_key and cfg.api_token)

    session = (
        db.query(models.GenerationSession)
        .filter(models.GenerationSession.id == session_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    test_cases = (
        db.query(models.TestCase)
        .filter(models.TestCase.session_id == session_id)
        .all()
    )

    project_key = cfg.project_key if cfg else "EUTEL"

    preview = [
        JiraImportPreview(
            tc_id=tc.tc_id,
            summary=tc.description[:100] + ("..." if len(tc.description) > 100 else ""),
            priority=tc.priority,
            issue_type="Story",
        )
        for tc in test_cases
    ]

    if configured:
        # Real Jira API call would go here once credentials are available
        # import requests
        # headers = {"Authorization": f"Basic {base64(email:token)}", ...}
        # for tc in test_cases:
        #     requests.post(f"{cfg.jira_url}/rest/api/2/issue", json={...}, headers=headers)
        message = (
            f"Ready to create {len(preview)} stories in {project_key} backlog. "
            "Live Jira integration will be activated once connectivity is confirmed."
        )
    else:
        message = (
            f"Jira is not configured yet. Save your Jira URL, project key, and API token "
            f"in Settings to activate live import. {len(preview)} stories are ready to be created in the backlog."
        )

    return JiraImportResponse(
        status="preview" if not configured else "ready",
        message=message,
        project_key=project_key,
        issues_preview=preview,
        configured=configured,
    )
