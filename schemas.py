from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class GenerateRequest(BaseModel):
    featureTitle: str
    description: str = ""
    module: str
    featureSelected: str = ""
    testType: str
    count: int = 15  # kept for compat, ignored by pipeline
    testerName: str = "Anonymous"


class TestCaseOut(BaseModel):
    id: int
    tc_id: str
    description: str
    type: str
    priority: str
    steps: str = ""
    expected_result: str = ""
    is_edited: bool = False
    confidence_score: float = 0.85
    hallucination_risk: str = "Low"

    class Config:
        from_attributes = True


class SessionOut(BaseModel):
    id: int
    feature_title: str
    description: str = ""
    module: str
    system: str = ""
    test_type: str
    tc_count: int
    rel_count: int
    tester_name: str
    from_cache: bool = False
    created_at: datetime
    test_cases: List[TestCaseOut] = []

    class Config:
        from_attributes = True


class SessionListItem(BaseModel):
    id: int
    feature_title: str
    module: str
    test_type: str
    tc_count: int
    tester_name: str
    from_cache: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class TestCaseUpdate(BaseModel):
    description: Optional[str] = None
    priority: Optional[str] = None
    steps: Optional[str] = None
    expected_result: Optional[str] = None


class FollowupRequest(BaseModel):
    query: str


class FollowupResponse(BaseModel):
    type: str        # "answer" | "new_cases"
    message: str
    new_cases: List[TestCaseOut] = []


class JiraConfigIn(BaseModel):
    jira_url: str = ""
    project_key: str = ""
    api_token: str = ""
    user_email: str = ""


class JiraConfigOut(BaseModel):
    jira_url: str
    project_key: str
    user_email: str
    configured: bool

    class Config:
        from_attributes = True


class JiraImportPreview(BaseModel):
    tc_id: str
    summary: str
    priority: str
    issue_type: str


class JiraImportResponse(BaseModel):
    status: str
    message: str
    project_key: str
    issues_preview: List[JiraImportPreview]
    configured: bool
