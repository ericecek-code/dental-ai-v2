"""POST /analyze — upload RTG → detekcia → výsledok.

Deň 1: ukladá len do dočasného priečinka a vracia JSON.
Deň 2: zápis do Supabase (analýzy, nálezy) + Storage (snímka, overlay, PDF).
"""

import anyio
import json
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.core.config import settings
from app.ml.detector import analyze_image

router = APIRouter()

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR = Path("data/results")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    conf: float = Query(default=None, ge=0.01, le=0.95),
    mode: str = Query(default="standard", pattern="^(standard|tiles|ens)$"),
):
    if not file.filename:
        raise HTTPException(400, "Chýba súbor.")

    max_bytes = settings.max_upload_mb * 1024 * 1024
    job_id = uuid.uuid4().hex[:12]
    # len čisté meno súboru — ochrana proti path traversal v filename
    safe_name = Path(file.filename).name or "upload.jpg"
    dest = UPLOAD_DIR / f"{job_id}_{safe_name}"
    size = 0
    with dest.open("wb") as f:
        while chunk := await file.read(1 << 20):
            size += len(chunk)
            if size > max_bytes:
                dest.unlink(missing_ok=True)
                raise HTTPException(413, f"Súbor väčší než {settings.max_upload_mb} MB.")
            f.write(chunk)

    started = time.time()

    def _infer():
        # synchronná CPU inferencia — beží vo worker threadpoolu (anyio),
        # nepatrí do event loopu: inak počas analýzy nezodpovie ani /health
        # INFER_LOCK: model je zdieľaný a MC dropout ho prepína do train() — dve súbežné
        # analýzy by jednej z nich vrátili stovky náhodných boxov (overené 250–264).
        from app.ml.detector import INFER_LOCK

        with INFER_LOCK:
            if mode == "tiles":
                from app.ml.sahi_detector import detect_tiled
                return detect_tiled(str(dest), conf=conf or settings.conf_threshold)
            if mode == "ens":
                from app.ml.ensemble import analyze_ensemble
                return analyze_ensemble(str(dest), conf=conf)
            return analyze_image(str(dest), conf=conf)

    try:
        findings = await anyio.to_thread.run_sync(_infer)
    except FileNotFoundError as e:
        raise HTTPException(503, str(e)) from e
    except ValueError as e:
        raise HTTPException(415, f"Nepodporovaný formát snímky: {e}") from e
    except Exception as e:
        raise HTTPException(500, f"Analýza zlyhala: {e}") from e
    duration_ms = int((time.time() - started) * 1000)

    result = {
        "job_id": job_id,
        "filename": file.filename,
        "duration_ms": duration_ms,
        "count": len(findings),
        "mode": mode,
        "findings": findings,
    }
    (RESULTS_DIR / f"{job_id}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result
