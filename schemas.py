from pydantic import BaseModel, field_validator
from typing import List, Optional
from datetime import datetime


class GenerateRequest(BaseModel):
    featureTitle: str
    description: Optional[str] = ""
    module: Optional[str] = ""        # empty → auto-detected from title+description
    featureSelected: Optional[str] = ""
    testType: Optional[str] = ""      # empty → generate all 5 test types in parallel
    release: Optional[str] = "R1"
    chainMode: Optional[bool] = False
    count: Optional[int] = 15
    testerName: Optional[str] = "Anonymous"

    @field_validator("description", "module", "featureSelected", "testType",
                     "release", "testerName", mode="before")
    @classmethod
    def none_to_default_str(cls, v):
        return v if v is not None else ""

    @field_validator("chainMode", mode="before")
    @classmethod
    def none_to_false(cls, v):
        return bool(v) if v is not None else False

    @field_validator("count", mode="before")
    @classmethod
    def none_to_fifteen(cls, v):
        return int(v) if v is not None else 15


class TestCaseOut(BaseModel):
    id: int
    tc_id: str
    description: str
    type: str
    priority: str
    steps: Optional[str] = ""
    expected_result: Optional[str] = ""
    is_edited: bool = False
    confidence_score: float = 0.85
    hallucination_risk: Optional[str] = "Low"
    automation_candidate: bool = False
    automation_notes: Optional[str] = ""

    class Config:
        from_attributes = True

    @field_validator("steps", "expected_result", "automation_notes", mode="before")
    @classmethod
    def none_to_empty_str(cls, v):
        return v if v is not None else ""

    @field_validator("hallucination_risk", mode="before")
    @classmethod
    def none_to_low(cls, v):
        return v if v is not None else "Low"


class SessionOut(BaseModel):
    id: int
    feature_title: str
    description: Optional[str] = ""
    module: Optional[str] = ""
    system: Optional[str] = ""
    test_type: Optional[str] = "Functional"
    release: Optional[str] = "R1"
    tc_count: Optional[int] = 0
    rel_count: Optional[int] = 0
    tester_name: Optional[str] = "Anonymous"
    from_cache: bool = False
    chain_mode: bool = False
    out_of_scope_warning: Optional[str] = ""
    created_at: datetime
    test_cases: List[TestCaseOut] = []

    class Config:
        from_attributes = True

    @field_validator(
        "description", "module", "system", "test_type", "release",
        "tester_name", "out_of_scope_warning", mode="before",
    )
    @classmethod
    def none_to_empty_str(cls, v):
        return v if v is not None else ""

    @field_validator("tc_count", "rel_count", mode="before")
    @classmethod
    def none_to_zero(cls, v):
        return v if v is not None else 0

    @property
    def is_multi(self) -> bool:
        return self.test_type == "Multi"


class SessionListItem(BaseModel):
    id: int
    feature_title: Optional[str] = ""
    module: Optional[str] = ""
    test_type: Optional[str] = "Functional"
    release: Optional[str] = "R1"
    tc_count: Optional[int] = 0
    tester_name: Optional[str] = "Anonymous"
    from_cache: bool = False
    chain_mode: bool = False
    created_at: datetime

    class Config:
        from_attributes = True

    @field_validator("feature_title", "module", "test_type", "release", "tester_name", mode="before")
    @classmethod
    def none_to_empty(cls, v):
        return v if v is not None else ""

    @field_validator("tc_count", mode="before")
    @classmethod
    def none_to_zero(cls, v):
        return v if v is not None else 0


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
