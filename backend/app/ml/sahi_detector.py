"""Tiled (SAHI-štýl) inferencia — malé kazy na veľkých RTG snímkach.

Model natrénovaný na 1280 px má na snímke 3000×2000 problém: kaz zaberá
20–40 px a po zmenšení na inference rozlíšenie zmizne. Táto modul snímku
rozreže na dlaždice s prekrytím, každú zistí zvlášť, boxy prepočíta
do globálnych súradníc a prekrytia zlúči vlastným NMS.

Výstup má rovnaký formát ako app.ml.detector.analyze_image.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import cv2

from app.ml.detector import CLASSES_SK, _tooth_number, load_model

TMP_DIR = Path("data/tmp")
TMP_DIR.mkdir(parents=True, exist_ok=True)


def _tile_starts(size: int, tile_size: int, step: int) -> list[int]:
    """Počiatočné súradnice dlaždíc po osi — posledná vždy dosiahne okraj."""
    if size <= tile_size:
        return [0]
    starts = list(range(0, size - tile_size + 1, step))
    if starts[-1] != size - tile_size:
        starts.append(size - tile_size)
    return starts


def _iou(a: list[float], b: list[float]) -> float:
    """Intersection over union dvoch boxov [x1, y1, x2, y2]."""
    iw = min(a[2], b[2]) - max(a[0], b[0])
    ih = min(a[3], b[3]) - max(a[1], b[1])
    if iw <= 0 or ih <= 0:
        return 0.0
    inter = iw * ih
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _nms(detections: list[dict], iou_threshold: float = 0.5) -> list[dict]:
    """Zlučí prekryvajúce sa detekcie per trieda — zostane najvyššia confidence."""
    kept: list[dict] = []
    for label in {d["label"] for d in detections}:
        by_conf = sorted(
            (d for d in detections if d["label"] == label),
            key=lambda d: d["confidence"],
            reverse=True,
        )
        while by_conf:
            best = by_conf.pop(0)
            kept.append(best)
            by_conf = [d for d in by_conf if _iou(best["bbox"], d["bbox"]) < iou_threshold]
    return kept


def _tile(img, x0: int, y0: int, tile_size: int):
    """Vytáže dlaždicu x0,y0, okraje doplní zrkadlovaním na tile_size.

    Vráti (patch, valid_w, valid_h) — valid_* je veľkosť reálneho obsahu bez paddingu.
    """
    h, w = img.shape[:2]
    x1, y1 = min(x0, w), min(y0, h)
    x2, y2 = min(x1 + tile_size, w), min(y1 + tile_size, h)
    patch = img[y1:y2, x1:x2]
    valid_h, valid_w = patch.shape[:2]
    pad_r = tile_size - valid_w
    pad_b = tile_size - valid_h
    if pad_r or pad_b:
        patch = cv2.copyMakeBorder(patch, 0, pad_b, 0, pad_r, cv2.BORDER_REFLECT_101)
    return patch, valid_w, valid_h


def detect_tiled(image_path: str, conf: float = 0.25, tile_size: int = 1024,
                 overlap: int = 200, imgsz: int = 1024) -> list[dict]:
    """Zistí nálezy po dlaždiciach. Vráti rovnaký formát ako analyze_image."""
    if tile_size <= 0:
        raise ValueError("tile_size musí byť > 0.")
    if not 0 <= overlap < tile_size:
        raise ValueError("overlap musí byť 0 <= overlap < tile_size.")

    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Nepodarilo sa načítať {image_path}")

    model = load_model()
    step = tile_size - overlap
    h, w = image.shape[:2]
    starts_x = _tile_starts(w, tile_size, step)
    starts_y = _tile_starts(h, tile_size, step)

    detections: list[dict] = []
    # unikatný prefix — dve súbežné požiadavky si súbory neprepíšu
    prefix = uuid.uuid4().hex[:12]
    index = 0

    for y0 in starts_y:
        for x0 in starts_x:
            index += 1
            tile_path = TMP_DIR / f"tile_{prefix}_{index:03d}.png"
            patch = None
            results = None
            try:
                patch, valid_w, valid_h = _tile(image, x0, y0, tile_size)
                if not cv2.imwrite(str(tile_path), patch):
                    raise RuntimeError(f"Nepodarilo sa uložiť dlaždicu {tile_path}")
                results = model.predict(
                    str(tile_path), imgsz=imgsz, conf=conf, device="cpu", verbose=False
                )
            finally:
                # PNG zmizne hneď po predikcii — na disku nezostáva ani jedna
                tile_path.unlink(missing_ok=True)
                patch = None

            for r in results:
                for box in r.boxes:
                    label = model.names[int(box.cls)]
                    tx1, ty1, tx2, ty2 = (float(v) for v in box.xyxy[0].tolist())
                    # orez na reálny obsah dlaždice — padding je zrkadlo, nie obraz
                    tx1, tx2 = min(max(tx1, 0.0), float(valid_w)), min(max(tx2, 0.0), float(valid_w))
                    ty1, ty2 = min(max(ty1, 0.0), float(valid_h)), min(max(ty2, 0.0), float(valid_h))
                    if tx2 - tx1 < 1 or ty2 - ty1 < 1:
                        continue  # box ležal celý v paddingu
                    # dlaždica -> originál: plus offset dlaždice
                    gx1, gy1 = min(tx1 + x0, float(w)), min(ty1 + y0, float(h))
                    gx2, gy2 = min(tx2 + x0, float(w)), min(ty2 + y0, float(h))
                    sk, severity, _ = CLASSES_SK.get(label, (label, "watch", "⚪"))
                    detections.append(
                        {
                            "label": label,
                            "label_sk": sk,
                            "severity": severity,
                            "confidence": round(float(box.conf), 3),
                            "bbox": [round(gx1), round(gy1), round(gx2), round(gy2)],
                            "tooth": _tooth_number((gx1 + gx2) / 2, (gy1 + gy2) / 2, w, h),
                        }
                    )
            results = None

    findings = _nms(detections, iou_threshold=0.5)
    findings.sort(key=lambda f: f["confidence"], reverse=True)
    return findings