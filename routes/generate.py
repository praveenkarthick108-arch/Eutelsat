import hashlib
import re
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
import models
from schemas import GenerateRequest, SessionOut
from ai_pipeline import run_pipeline, client
from scope_data import SCOPE, RELATED
from rag import retriever as rag_retriever

router = APIRouter()

CACHE_TTL_DAYS = 7
FUZZY_THRESHOLD = 0.70


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _cache_key(module: str, feature_title: str, test_type: str) -> str:
    normalized = _normalize(f"{module} {feature_title} {test_type}")
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _jaccard(a: str, b: str) -> float:
    wa = set(_normalize(a).split())
    wb = set(_normalize(b).split())
    if not wa and not wb:
        return 1.0
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def _find_cache(module: str, feature_title: str, test_type: str, db: Session):
    now = datetime.utcnow()
    key = _cache_key(module, feature_title, test_type)
    exact = (
        db.query(models.QueryCache)
        .filter(models.QueryCache.cache_key == key, models.QueryCache.expires_at > now)
        .first()
    )
    if exact:
        return exact, "exact"

    candidates = (
        db.query(models.QueryCache)
        .filter(
            models.QueryCache.module == module,
            models.QueryCache.test_type == test_type,
            models.QueryCache.expires_at > now,
        )
        .all()
    )
    for entry in candidates:
        sim = _jaccard(feature_title, entry.feature_title_normalized)
        if sim >= FUZZY_THRESHOLD:
            return entry, f"fuzzy ({sim:.0%} match)"

    return None, None


def _store_cache(module: str, feature_title: str, test_type: str, session_id: int, db: Session):
    key = _cache_key(module, feature_title, test_type)
    db.query(models.QueryCache).filter(models.QueryCache.cache_key == key).delete()
    entry = models.QueryCache(
        cache_key=key,
        feature_title_normalized=_normalize(feature_title),
        module=module,
        test_type=test_type,
        session_id=session_id,
        expires_at=datetime.utcnow() + timedelta(days=CACHE_TTL_DAYS),
    )
    db.add(entry)


@router.post("/generate", response_model=SessionOut)
def generate_test_cases(req: GenerateRequest, db: Session = Depends(get_db)):
    # Cache check
    cache_entry, match_type = _find_cache(req.module, req.featureTitle, req.testType, db)
    if cache_entry:
        cached_session = (
            db.query(models.GenerationSession)
            .filter(models.GenerationSession.id == cache_entry.session_id)
            .first()
        )
        if cached_session:
            print(f"[Cache HIT] {match_type} -> session #{cached_session.id}")
            cache_entry.hits += 1
            db.commit()
            return cached_session

    # RAG context retrieval
    rag_query = f"{req.featureTitle} {req.module} {req.testType}"
    try:
        rag_context = rag_retriever.retrieve(rag_query, db, client)
    except Exception as e:
        print(f"[RAG] Retrieval failed (non-fatal): {e}")
        rag_context = ""

    # Run AI pipeline
    try:
        test_cases = run_pipeline(
            req.featureTitle, req.description, req.module, req.testType,
            rag_context, getattr(req, "release", "R1")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI pipeline failed: {str(e)}")

    system = SCOPE.get(req.module, {}).get("system", "")
    rel_count = len(RELATED.get(req.module, []))

    session = models.GenerationSession(
        feature_title=req.featureTitle,
        description=req.description,
        module=req.module,
        system=system,
        test_type=req.testType,
        tc_count=len(test_cases),
        rel_count=rel_count,
        tester_name=req.testerName or "Anonymous",
        from_cache=False,
    )
    db.add(session)
    db.flush()

    for i, tc in enumerate(test_cases):
        tc_obj = models.TestCase(
            session_id=session.id,
            tc_id=f"TC-{str(i + 1).zfill(3)}",
            description=tc.get("description", f"Verify that test case {i+1} passes"),
            type=req.testType,
            priority=tc.get("priority", "Medium"),
            steps=tc.get("steps", ""),
            expected_result=tc.get("expected_result", ""),
            confidence_score=tc.get("confidence_score", 0.82),
            hallucination_risk=tc.get("hallucination_risk", "Low"),
        )
        db.add(tc_obj)

    db.flush()
    _store_cache(req.module, req.featureTitle, req.testType, session.id, db)
    db.commit()
    db.refresh(session)
    return session
