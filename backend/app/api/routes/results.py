"""GET /results — zoznam a detail uložených analýz; POST feedback zubara."""

import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.routes.analyze import RESULTS_DIR
from app.ml.database import _conn, get_feedback, save_feedback

router = APIRouter()


class Feedback(BaseModel):
    index: int
    status: str  # "confirmed" | "corrected"


@router.get("/metrics")
def metrics():
    """Zhoda AI s lekárom — kľúčové číslo pre budovanie dôvery."""
    conn = _conn()
    try:
        confirmed = conn.execute(
            "SELECT COUNT(*) FROM findings_feedback WHERE status='confirmed'"
        ).fetchone()[0]
        corrected = conn.execute(
            "SELECT COUNT(*) FROM findings_feedback WHERE status='corrected'"
        ).fetchone()[0]
        cases = conn.execute(
            "SELECT COUNT(DISTINCT job_id) FROM findings_feedback"
        ).fetchone()[0]
    finally:
        conn.close()
    total = confirmed + corrected
    return {
        "cases_reviewed": cases,
        "confirmed": confirmed,
        "corrected": corrected,
        "agreement_pct": round(100 * confirmed / total, 1) if total else None,
    }


@router.get("/results")
def list_results(limit: int = 50):
    files = sorted(RESULTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    out = []
    for p in files[:limit]:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        out.append(
            {
                "job_id": data.get("job_id"),
                "filename": data.get("filename"),
                "count": data.get("count"),
                "duration_ms": data.get("duration_ms"),
            }
        )
    return {"items": out, "total": len(files)}


@router.get("/results/{job_id}")
def get_result(job_id: str):
    # Validate job_id format to prevent path traversal
    if not re.fullmatch(r"[0-9a-f]{12}", job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID format")
    p = RESULTS_DIR / f"{job_id}.json"
    if not p.exists():
        raise HTTPException(404, f"Výsledok {job_id} nenájdený.")
    data = json.loads(p.read_text(encoding="utf-8"))
    # Frontend (api.ts) deklaráje feedback ako pole a volá na nom .forEach().
    # Vracať dict {index: status} sa serializuje na JSON objekt, kde kľúč je string
    # -> TypeError "feedback.forEach is not a function" v prehliadači, ktorý zhadil
    # celý výsledok analýzy (a snímka zmizla z obrazovky).
    data["feedback"] = [
        {"index": int(idx), "status": status}
        for idx, status in sorted(get_feedback(job_id).items())
    ]
    return data


@router.post("/results/{job_id}/feedback")
def post_feedback(job_id: str, fb: Feedback):
    if fb.status not in ("confirmed", "corrected"):
        raise HTTPException(422, "status musí byť 'confirmed' alebo 'corrected'.")
    save_feedback(job_id, fb.index, fb.status)
    return {"ok": True, "job_id": job_id, "index": fb.index, "status": fb.status}
