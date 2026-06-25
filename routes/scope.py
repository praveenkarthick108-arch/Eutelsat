from fastapi import APIRouter
from scope_data import SCOPE, RELATED, MATCH_PCT

router = APIRouter()


@router.get("/scope")
def get_scope():
    return {"scope": SCOPE, "related": RELATED, "matchPct": MATCH_PCT}
