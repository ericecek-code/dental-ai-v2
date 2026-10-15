"""POST /vision/{job_id} — AI druhý názor (Gemini VLM) + párovanie s YOLO nálezmi.

Route je def → FastAPI beží v threadpoole (REST volanie ~5-15 s je v bezpečí).
Vyžaduje GEMINI_API_KEY (Space secrets / .env).
"""

import json
import re
from pathlib import Path

import cv2
from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["vision"])

DATA = Path("data")
RESULTS = DATA / "results"


def _load_upload_image(job_id: str):
    matches = sorted((DATA / "uploads").glob(f"{job_id}_*"))
    if not matches:
        raise HTTPException(404, f"Snímka pre {job_id} nenájdená.")
    img = cv2.imread(str(matches[0]))
    if img is None:
        raise HTTPException(415, "Nepodporovaný formát snímky.")
    return img


@router.post("/vision/{job_id}")
def vision_second_opinion(job_id: str):
    # Validate job_id format to prevent path traversal
    if not re.fullmatch(r"[0-9a-f]{12}", job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID format")
    result_path = RESULTS / f"{job_id}.json"
    if not result_path.exists():
        raise HTTPException(404, f"Výsledok {job_id} nenájdený.")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    yolo_findings = result.get("findings", [])

    img = _load_upload_image(job_id)

    try:
        from app.ml.gemini_vision import (
            analyze_xray_with_gemini,
            attach_tooth_bbox_estimates,
            match_yolo_gemini,
        )

        gem = analyze_xray_with_gemini(img)
        detections = attach_tooth_bbox_estimates(list(gem.get("gemini_detections", [])), img.shape[:2])
        gem["gemini_detections"] = detections
        comparison = match_yolo_gemini(yolo_findings, detections)
    except Exception as e:
        raise HTTPException(500, f"VLM druhý názor zlyhal: {e}") from e

    return {
        "job_id": job_id,
        "success": gem.get("success", False),
        "error": gem.get("error"),
        "model": gem.get("model"),
        "overall_assessment": gem.get("overall_assessment", ""),
        "gemini_detections": gem.get("gemini_detections", []),
        "processing_time_ms": gem.get("processing_time_ms", 0),
        "comparison": comparison,
    }
