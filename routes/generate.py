import hashlib
import re
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
import models
from schemas import GenerateRequest, SessionOut
from ai_pipeline import (
    run_pipeline, check_out_of_scope, detect_module, client, _p,
    TEST_TYPES_MULTI, TC_TYPE_PREFIX,
)
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


def _run_type_pipeline(feature_title, description, module, test_type, rag_context, release):
    """Run a single test-type pipeline — called from ThreadPoolExecutor."""
    chain = (test_type == "End-to-End (E2E)")
    try:
        cases = run_pipeline(
            feature_title, description, module, test_type,
            rag_context, release, chain_mode=chain, multi_mode=True,
        )
        return test_type, cases
    except Exception as e:
        _p(f"[Multi-Gen] {test_type} failed: {e}")
        return test_type, []


@router.post("/generate", response_model=SessionOut)
def generate_test_cases(req: GenerateRequest, db: Session = Depends(get_db)):
    try:
        return _generate_inner(req, db)
    except HTTPException:
        raise
    except Exception as exc:
        tb = traceback.format_exc()
        print(f"[Generate] UNHANDLED: {exc}\n{tb}")
        raise HTTPException(status_code=500, detail=f"Server error: {exc}")


def _generate_inner(req: GenerateRequest, db: Session):
    chain_mode = getattr(req, "chainMode", False)
    release = getattr(req, "release", "R1")
    multi_mode = not bool(req.testType)  # empty testType → generate all 5 types

    # Auto-detect module if not provided
    module = req.module.strip() if req.module else ""
    if not module:
        module = detect_module(req.featureTitle, req.description)
        _p(f"[Module] Auto-detected: {module}")

    # Out-of-scope check (warn but still generate)
    oos_warning = check_out_of_scope(req.featureTitle, req.testType or "All", req.description)

    # Cache check — only for single-type, non-chain requests
    if not multi_mode and not chain_mode and req.testType:
        cache_entry, match_type = _find_cache(module, req.featureTitle, req.testType, db)
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
    rag_query = f"{req.featureTitle} {module} {req.testType or 'All'}"
    try:
        rag_context = rag_retriever.retrieve(rag_query, db, client)
    except Exception as e:
        print(f"[RAG] Retrieval failed (non-fatal): {e}")
        rag_context = ""

    if multi_mode:
        # ── Parallel multi-type generation ──────────────────────────────────
        _p(f"[Multi-Gen] Launching {len(TEST_TYPES_MULTI)} type pipelines in parallel...")
        all_type_cases: dict = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(
                    _run_type_pipeline,
                    req.featureTitle, req.description, module, tt, rag_context, release,
                ): tt
                for tt in TEST_TYPES_MULTI
            }
            for future in as_completed(futures):
                tt, cases = future.result()
                all_type_cases[tt] = cases
                _p(f"[Multi-Gen] {tt}: {len(cases)} cases")

        # Combine — preserve ordered type grouping with prefixed TC IDs
        test_cases: list[dict] = []
        for tt in TEST_TYPES_MULTI:
            prefix = TC_TYPE_PREFIX.get(tt, "TC")
            for i, tc in enumerate(all_type_cases.get(tt, []), 1):
                tc["type"] = tt
                tc["tc_id"] = f"{prefix}-{str(i).zfill(3)}"
                test_cases.append(tc)

        test_type_label = "Multi"

    else:
        # ── Single-type generation (backward compat) ─────────────────────────
        try:
            test_cases = run_pipeline(
                req.featureTitle, req.description, module, req.testType,
                rag_context, release, chain_mode,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"AI pipeline failed: {str(e)}")
        test_type_label = req.testType

    system = SCOPE.get(module, {}).get("system", "")
    rel_count = len(RELATED.get(module, []))

    session = models.GenerationSession(
        feature_title=req.featureTitle,
        description=req.description,
        module=module,
        system=system,
        test_type=test_type_label,
        release=release,
        tc_count=len(test_cases),
        rel_count=rel_count,
        tester_name=req.testerName or "Anonymous",
        from_cache=False,
        chain_mode=chain_mode,
        out_of_scope_warning=oos_warning,
    )
    db.add(session)
    db.flush()

    for i, tc in enumerate(test_cases):
        tc_id = tc.get("tc_id") or f"TC-{str(i + 1).zfill(3)}"
        tc_obj = models.TestCase(
            session_id=session.id,
            tc_id=tc_id,
            description=tc.get("description", f"Verify test case {i + 1}"),
            type=tc.get("type") or req.testType or "Functional",
            priority=tc.get("priority", "Medium"),
            steps=tc.get("steps", ""),
            expected_result=tc.get("expected_result", ""),
            confidence_score=tc.get("confidence_score", 0.82),
            hallucination_risk=tc.get("hallucination_risk", "Low"),
            automation_candidate=bool(tc.get("automation_candidate", False)),
            automation_notes=tc.get("automation_notes", ""),
        )
        db.add(tc_obj)

    db.flush()
    if not multi_mode and not chain_mode and req.testType:
        _store_cache(module, req.featureTitle, req.testType, session.id, db)
    db.commit()
    db.refresh(session)
    return session
