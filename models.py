from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from database import Base


class GenerationSession(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    feature_title = Column(String(500), nullable=False)
    description = Column(Text, default="")
    module = Column(String(200), nullable=False)
    system = Column(String(200), default="")
    test_type = Column(String(100), nullable=False)
    tc_count = Column(Integer, default=0)
    rel_count = Column(Integer, default=0)
    tester_name = Column(String(200), default="Anonymous")
    from_cache = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    test_cases = relationship(
        "TestCase",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="TestCase.tc_id"
    )


class TestCase(Base):
    __tablename__ = "test_cases"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    tc_id = Column(String(20), nullable=False)
    description = Column(Text, nullable=False)
    type = Column(String(100), nullable=False)
    priority = Column(String(20), nullable=False)
    steps = Column(Text, default="")
    expected_result = Column(Text, default="")
    is_edited = Column(Boolean, default=False)
    confidence_score = Column(Float, default=0.85)
    hallucination_risk = Column(String(20), default="Low")

    session = relationship("GenerationSession", back_populates="test_cases")


class QueryCache(Base):
    __tablename__ = "query_cache"

    id = Column(Integer, primary_key=True, index=True)
    cache_key = Column(String(64), unique=True, index=True, nullable=False)
    feature_title_normalized = Column(String(500), nullable=False)
    module = Column(String(200), nullable=False)
    test_type = Column(String(100), nullable=False)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    hits = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(days=7))


class JiraConfig(Base):
    __tablename__ = "jira_config"

    id = Column(Integer, primary_key=True, index=True)
    jira_url = Column(String(500), default="")
    project_key = Column(String(50), default="")
    api_token = Column(String(500), default="")
    user_email = Column(String(200), default="")
    updated_at = Column(DateTime, default=datetime.utcnow)
