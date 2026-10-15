"""GET /report/{job_id} — pacientsky PDF; GET /gradcam/{job_id} — heatmapa; GET /uploads/{job_id} — originálna snímka."""

import glob
import json
import re
from pathlib import Path

import cv2
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

from app.ml.gradcam import generate_gradcam

router = APIRouter()

DATA = Path("data")
UPLOADS = DATA / "uploads"
RESULTS = DATA / "results"


def _find_image(job_id: str) -> Path:
    # job_id generuje server (uuid hex 12) — validácia chráni glob pred * ? [
    if not re.fullmatch(r"[0-9a-f]{12}", job_id):
        raise HTTPException(400, "Neplatný job_id.")
    matches = sorted(UPLOADS.glob(f"{job_id}_*"))
    if not matches:
        raise HTTPException(404, f"Snímka pre {job_id} nenájdená.")
    return matches[0]


def _find_result(job_id: str) -> dict:
    p = RESULTS / f"{job_id}.json"
    if not p.exists():
        raise HTTPException(404, f"Výsledok {job_id} nenájdený.")
    return json.loads(p.read_text(encoding="utf-8"))


def _draw_overlay(image_path: Path, findings: list[dict]) -> Path:
    out_dir = DATA / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{image_path.stem}_overlay.png"

    img = cv2.imread(str(image_path))
    if img is None:
        raise HTTPException(415, f"Nepodporovaný formát obrázka: {image_path.name}")
    colors = {"urgent": (68, 68, 239), "treat_soon": (11, 158, 245), "watch": (238, 189, 56)}
    for f in findings:
        x1, y1, x2, y2 = f["bbox"]
        c = colors.get(f.get("severity"), (200, 200, 200))
        cv2.rectangle(img, (x1, y1), (x2, y2), c, 3)
        label = f"{f.get('label', '?')} {f.get('confidence', 0) * 100:.0f}%"
        cv2.putText(img, label, (x1, max(25, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.1, c, 2, cv2.LINE_AA)
    cv2.imwrite(str(out_path), img)
    return out_path


@router.get("/report/{job_id}")
def report(job_id: str):
    result = _find_result(job_id)
    image = _find_image(job_id)
    overlay = _draw_overlay(image, result.get("findings", []))

    try:
        from app.ml.reporter import generate_patient_report
    except ImportError as e:
        raise HTTPException(503, f"Reporter nie je dostupný: {e}") from e

    pdf_path = DATA / "reports" / f"{job_id}_report.pdf"
    generate_patient_report(
        out_path=str(pdf_path),
        filename=result.get("filename", image.name),
        findings=result.get("findings", []),
        overlay_image_path=str(overlay),
    )
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"dental-ai-posudok-{job_id}.pdf",
    )


@router.get("/gradcam/{job_id}")
def gradcam(job_id: str):
    result = _find_result(job_id)
    image = _find_image(job_id)
    findings = result.get("findings", [])
    # cieľová trieda = prvý nález z hlavných tried (mega5 restaurácie v Grad-CAM modeli nie sú → None)
    class_id = None
    if findings:
        order = ["Impacted", "Caries", "Periapical Lesion", "Deep Caries"]
        top = next((f["label"] for f in findings if f["label"] in order), None)
        class_id = order.index(top) if top else None

    try:
        from app.ml.detector import INFER_LOCK

        # rovnaký zámok ako /analyze — Grad-CAM pracuje s tým istým zdieľaným modelom
        with INFER_LOCK:
            overlay = generate_gradcam(str(image), class_id=class_id)
    except Exception as e:
        raise HTTPException(500, f"Grad-CAM zlyhal: {e}") from e

    ok, png = cv2.imencode(".png", overlay)
    if not ok:
        raise HTTPException(500, "Kódovanie PNG zlyhalo.")
    return Response(content=png.tobytes(), media_type="image/png")


@router.get("/uploads/{job_id}")
def upload(job_id: str):
    image = _find_image(job_id)
    return FileResponse(image)