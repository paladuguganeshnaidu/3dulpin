"""AI + LLM assistant routes.

The assistant never mutates authoritative records and never fabricates GIS
answers: it dispatches natural-language questions to a fixed set of safe,
read-only backend query tools and answers from the returned data. When an
OpenRouter key is configured it may phrase the answer; otherwise it degrades
to a clear local tool response (offline/demo mode works regardless).
"""
from __future__ import annotations

import json
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.enums import Role
from ..db.models import Parcel, Property, ValidationResult
from ..db.session import get_db
from ..ml.registry import registry
from ..services.catalog import parcel_to_dict, property_to_dict
from .deps import get_current_user, require_roles

router = APIRouter(prefix="/ai", tags=["ai"])


# ---------------------------------------------------------------------------
# Tool registry (safe read-only query tools)
# ---------------------------------------------------------------------------

def tool_search_parcels(db: Session, q: str) -> dict:
    rows = db.execute(select(Parcel).where(Parcel.ref_id.like(f"%{q}%")).limit(20)).scalars().all()
    return {"tool": "search_parcels", "items": [parcel_to_dict(p) for p in rows]}


def tool_search_ulpin(db: Session, q: str) -> dict:
    p = db.execute(select(Property).where(Property.ulpin == q.upper())).scalar_one_or_none()
    return {"tool": "search_ulpin", "items": [property_to_dict(p)] if p else []}


def tool_get_property(db: Session, q: str) -> dict:
    p = db.execute(select(Property).where(Property.ref_key == q)).scalar_one_or_none()
    return {"tool": "get_property", "items": [property_to_dict(p)] if p else []}


def tool_get_building(db: Session, q: str) -> dict:
    stmt = select(Property).where(Property.property_type == "building")
    if q:
        stmt = stmt.where(Property.ref_key.like(f"%{q}%") | Property.name.like(f"%{q}%"))
    rows = db.execute(stmt.limit(20)).scalars().all()
    return {"tool": "get_building", "items": [property_to_dict(p) for p in rows]}


def tool_get_floors(db: Session, q: str) -> dict:
    b = db.execute(select(Property).where(Property.ref_key == q)).scalar_one_or_none()
    if b is None:
        return {"tool": "get_floors", "items": []}
    rows = db.execute(select(Property).where(Property.parent_id == b.id, Property.property_type == "floor")).scalars().all()
    return {"tool": "get_floors", "building": q, "items": [property_to_dict(p) for p in rows]}


def tool_get_conflicts(db: Session, _q: str) -> dict:
    latest = db.execute(
        select(ValidationResult).where(ValidationResult.scope_key == "global").order_by(ValidationResult.created_at.desc())
    ).scalars().first()
    issues = [i for i in (latest.issues if latest else []) if i.get("state") in ("CONFLICT", "ERROR")] if latest else []
    return {"tool": "get_conflicts", "items": issues}


def tool_inspect_validation(db: Session, _q: str) -> dict:
    latest = db.execute(
        select(ValidationResult).where(ValidationResult.scope_key == "global").order_by(ValidationResult.created_at.desc())
    ).scalars().first()
    return {"tool": "inspect_validation",
            "items": [{"scope": latest.scope_key, "state": latest.state,
                       "summary": latest.summary}] if latest else []}


def tool_search_by_location(db: Session, q: str) -> dict:
    rows = db.execute(
        select(Property).where(Property.name.like(f"%{q}%") | Property.ref_key.like(f"%{q}%")).limit(20)
    ).scalars().all()
    return {"tool": "search_by_location", "items": [property_to_dict(p) for p in rows]}


TOOLS: dict[str, Callable[[Session, str], dict]] = {
    "search_parcels": tool_search_parcels,
    "search_ulpin": tool_search_ulpin,
    "get_property": tool_get_property,
    "get_building": tool_get_building,
    "get_floors": tool_get_floors,
    "get_conflicts": tool_get_conflicts,
    "inspect_validation": tool_inspect_validation,
    "search_by_location": tool_search_by_location,
}

TOOL_DOCS = [
    {"name": k, "description": f.__doc__ or "", "input": "text query"}
    for k, f in TOOLS.items()
]


def _route_query(message: str) -> tuple[str, str]:
    """Map a natural-language message to (tool, query). Deterministic fallback."""
    m = message.lower()
    if "conflict" in m or "overlap" in m or "topology" in m:
        return "get_conflicts", ""
    if "ulpin" in m or "identifier" in m:
        parts = m.replace("ulpin", " ").split()
        token = next((p for p in parts if p.isalnum() and len(p) > 6), "")
        return "search_ulpin", token
    if "validation" in m or "valid" in m or "inspect" in m:
        return "inspect_validation", ""
    if "floor" in m:
        token = next((p for p in m.replace("floor", " ").replace("floors", " ").split() if p.startswith("B") or p.isdigit()), "")
        return "get_floors", token
    if "building" in m:
        token = next((p for p in m.replace("building", " ").replace("buildings", " ").split() if p.startswith("B")), "")
        return "get_building", token
    if "parcel" in m:
        token = next((p for p in m.replace("parcel", " ").replace("parcels", " ").split() if p.startswith("P")), "")
        return "search_parcels", token
    if "underground" in m or "basement" in m or "utility" in m or "sewer" in m:
        return "search_by_location", "underground"
    return "search_by_location", ""


async def _openrouter_phrasing(message: str, tool_result: dict) -> str | None:
    """Optionally phrase a tool result with an LLM. Returns None when unavailable."""
    settings = get_settings()
    if not settings.openrouter_api_key:
        return None
    try:
        import httpx

        payload = {
            "model": settings.openrouter_model,
            "messages": [
                {"role": "system", "content":
                    "You answer property questions strictly from the supplied tool data. "
                    "Do not invent cadastral facts. State when data is synthetic/demo."},
                {"role": "user", "content": message},
                {"role": "assistant", "content": "Tool result:\n" + json.dumps(tool_result, default=str)[:6000]},
            ],
            "max_tokens": 400,
        }
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
                json=payload,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
    except Exception:
        return None
    return None


@router.get("/models")
def list_models(user=Depends(get_current_user)):
    return {"models": registry()}


@router.post("/analyse")
def ai_analyse(
    payload: dict | None = None,
    db: Session = Depends(get_db),
    user=Depends(require_roles(Role.SURVEYOR, Role.ADMIN)),
):
    from datetime import datetime, timezone

    from ..ml.analysis import analyse_dataset

    parcel_ref = (payload or {}).get("parcel_id") or (payload or {}).get("parcel_ref")
    result = analyse_dataset(db, parcel_ref=parcel_ref)
    result["generated_at"] = datetime.now(timezone.utc).isoformat()
    # persist an ai_predictions audit trail of this analysis
    from ..db.models import AiPrediction

    db.add(AiPrediction(
        prediction_type="assistive_analysis",
        input_ref=parcel_ref or "global",
        output={"summary": result["summary"], "anomaly_count": len(result["anomalies"]),
                "ai_candidate_count": len(result["ai_candidates"])},
        model_name="ai-assist/analysis-pipeline-v0",
        model_version="0.1.0",
        confidence=None,
        requires_verification=True,
    ))
    db.commit()
    return result


@router.post("/assistant/query")
async def assistant_query(
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(require_roles(Role.VIEWER, Role.SURVEYOR, Role.ADMIN)),
):
    message = str((payload or {}).get("message", "")).strip()
    if not message:
        raise HTTPException(422, "message is required.")
    tool_name, q = _route_query(message)
    fn = TOOLS.get(tool_name)
    if fn is None:
        raise HTTPException(422, "No tool available for that request.")
    tool_result = fn(db, q)

    phrasing = await _openrouter_phrasing(message, tool_result)
    answer = phrasing or _local_answer(message, tool_result)
    return {
        "message": message,
        "tool": tool_name,
        "tool_result": tool_result,
        "answer": answer,
        "offline": phrasing is None,
        "tools_available": list(TOOLS.keys()),
        "notice": "Answers are based on stored GIS data; nothing is legally authoritative.",
    }


def _local_answer(message: str, tool_result: dict) -> str:
    items = tool_result.get("items", [])
    if tool_result.get("tool") in ("get_conflicts", "inspect_validation"):
        if not items:
            return "No active issues found in the last validation run."
        return f"Last validation found {len(items)} issue(s). Inspect them on the map for details."
    if not items:
        return f"No stored objects matched '{message}'. (Offline tool result; enable OpenRouter for phrasing.)"
    return (f"Found {len(items)} result(s) from {tool_result['tool']}. "
            "Review them on the map. Note: this is assistive and based on stored GIS data.")
