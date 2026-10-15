"""Ensemble dvoch modelov — v8s (recall, nájde viac) + v8m (precision, menej falošných).

Zhodný nález oboch modelov dostane istotný bonus — „dva hlasy" sú pre zubara
dôveryhodnejšie než jeden. Výstup má rovnaký formát ako detector.analyze_image.
"""

from pathlib import Path

from app.core.config import settings
from app.ml.detector import _extract_findings, _iou, load_model

_V8M = None
V8M_WEIGHTS = Path(__file__).resolve().parents[2] / "weights" / "best_v8m_dentex.pt"
AGREEMENT_BOOST = 0.06


def _load_v8m():
    global _V8M
    if _V8M is None:
        from ultralytics import YOLO

        if not V8M_WEIGHTS.exists():
            raise FileNotFoundError(f"Chýbajú váhy ensemble modelu: {V8M_WEIGHTS}")
        _V8M = YOLO(str(V8M_WEIGHTS))
    return _V8M


def analyze_ensemble(image_path: str, conf: float | None = None) -> list[dict]:
    threshold = conf or settings.conf_threshold
    primary = load_model()          # v8s — hlavný "nálezc"
    secondary = _load_v8m()         # v8m — "potvrdzovateľ"

    # primár necháme pozrieť aj pod prah — chceme recall; sekundár striktne
    r_primary = primary.predict(image_path, conf=threshold * 0.7, imgsz=1280,
                                device="cpu", verbose=False)
    r_secondary = secondary.predict(image_path, conf=threshold, imgsz=1280,
                                    device="cpu", verbose=False)

    prim = _extract_findings(r_primary, primary)
    sec = _extract_findings(r_secondary, secondary)

    merged: list[dict] = []
    for f in prim:
        agree = next((s for s in sec
                      if s["label"] == f["label"] and _iou(s["bbox"], f["bbox"]) >= 0.55), None)
        if agree is not None:
            sec.remove(agree)
            f = {**f, "confidence": round(min(0.99, max(f["confidence"], agree["confidence"]) + AGREEMENT_BOOST), 3)}
        merged.append(f)
    # nález, ktorý videl len v8m, je vysoko presný — pridáme ho tiež
    merged.extend(sec)
    merged.sort(key=lambda f: f["confidence"], reverse=True)
    return merged
