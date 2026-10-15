"""YOLO detektor — lenivé načítanie váh, CPU inferencia s Test-Time Augmentation a nejistotou.

Triedy zodpovedajú váham z DentalXrayAI (DENTEX):
0 Impacted, 1 Caries, 2 Periapical Lesion, 3 Deep Caries.
Po retréningu na Kaggle stačí vymeniť weights/best.pt.
"""

import tempfile
import threading
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from app.core.config import settings
from app.ml.preprocessor import apply_clahe
import math
TTA_CONF_BOOST = 0.03

# Jedna inferencia naraz: model (aj mega5 / v8m) je zdieľaný v rámci procesu a MC dropout
# ho prepína do train() režimu. Bez zámku vidí druhá súbežná analýza aktívny dropout a vráti
# stovky náhodných boxov s conf ≈ 0,5 (overené: 4 súbežné behy → 257/250/264/9 nálezov).
INFER_LOCK = threading.RLock()

def _nms_per_class(detections: list[dict], iou_threshold: float = 0.5) -> list[dict]:
    """Non-maximum suppression per class."""
    kept = []
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


def _weighted_box_fusion(
    detections: list[dict],
    iou_threshold: float = 0.55,
) -> list[dict]:
    """Weighted Box Fusion — average boxes weighted by confidence."""
    if not detections:
        return []

    fused = []
    used = [False] * len(detections)

    for i, d1 in enumerate(detections):
        if used[i]:
            continue
        cluster = [d1]
        used[i] = True
        for j, d2 in enumerate(detections):
            if used[j] or d1["label"] != d2["label"]:
                continue
            if _iou(d1["bbox"], d2["bbox"]) >= iou_threshold:
                cluster.append(d2)
                used[j] = True

        # Weighted average
        total_conf = sum(d["confidence"] for d in cluster)
        if total_conf == 0:
            fused.append(d1)
            continue

        x1 = sum(d["bbox"][0] * d["confidence"] for d in cluster) / total_conf
        y1 = sum(d["bbox"][1] * d["confidence"] for d in cluster) / total_conf
        x2 = sum(d["bbox"][2] * d["confidence"] for d in cluster) / total_conf
        y2 = sum(d["bbox"][3] * d["confidence"] for d in cluster) / total_conf
        conf = max(d["confidence"] for d in cluster) + TTA_CONF_BOOST * (len(cluster) - 1)

        fused.append({
            **d1,
            "bbox": [round(x1), round(y1), round(x2), round(y2)],
            "confidence": round(min(0.99, conf), 3),
        })

    return fused

CLASSES_SK = {
    "Impacted": ("Retinovaný zub", "watch", "🟠"),
    "Caries": ("Kaz", "urgent", "🔴"),
    "Periapical Lesion": ("Periapikálna lézia", "treat_soon", "🟣"),
    "Deep Caries": ("Hlboký kaz", "urgent", "🔴"),
}

# Restaurácie z mega5 modelu — nie sú patológiou, ale dôležitý stav zuba
MEGA5_CLASSES_SK = {
    "Crown": ("Korunka", "restoration", "🟪"),
    "Filling": ("Plomba", "restoration", "🟦"),
    "Implant": ("Implantát", "restoration", "⚙️"),
}

MEGA5_WEIGHTS = Path(__file__).resolve().parents[2] / "weights" / "best_v8s_mega5.pt"
_mega5 = None


def load_model_mega5():
    global _mega5
    if _mega5 is None:
        from ultralytics import YOLO

        if not MEGA5_WEIGHTS.exists():
            raise FileNotFoundError(f"Chýbajú váhy restauračného modelu: {MEGA5_WEIGHTS}")
        _mega5 = YOLO(str(MEGA5_WEIGHTS))
    return _mega5

_model = None


def _iou(box1: list[int], box2: list[int]) -> float:
    """Vypočíta IoU dvoch bounding boxov vo formáte [x1, y1, x2, y2]."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    inter = max(0, x2 - x1) * max(0, y2 - y1)
    if inter == 0:
        return 0.0

    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = area1 + area2 - inter
    return inter / union


class MCDropoutWrapper(nn.Module):
    """Wrapper that injects dropout after Conv layers in Detect head during training mode."""
    
    def __init__(self, module: nn.Module, dropout_rate: float):
        super().__init__()
        self.module = module
        self.dropout_rate = dropout_rate
        
    def forward(self, x):
        out = self.module(x)
        if self.training and self.dropout_rate > 0:
            out = F.dropout(out, p=self.dropout_rate, training=True)
        return out


def _inject_mc_dropout(model, dropout_rate: float):
    """Inject MC Dropout do konvolúcií Detect headu — rekurzívne cez Sequential cv2/cv3.

    Detect head obsahuje cv2/cv3 ako nn.Sequential z ultralytics Conv modulov; samotný
    nn.Conv2d leží vnútri (attr `conv`). Bez rekurzie injekcia nič nezbalí → dropout mŕtvy.
    """
    from ultralytics.nn.modules.head import Detect

    def _wrap(module):
        for name, child in module.named_children():
            if isinstance(child, nn.Conv2d):
                setattr(module, name, MCDropoutWrapper(child, dropout_rate))
            elif list(child.children()):
                _wrap(child)

    for module in model.modules():
        if isinstance(module, Detect):
            _wrap(module)


def load_model():
    global _model
    if _model is None:
        from ultralytics import YOLO

        weights = Path(settings.weights_path)
        if not weights.exists():
            raise FileNotFoundError(
                f"Chýbajú váhy: {weights}. Stiahni best.pt (pozri README) alebo spusti tréning."
            )
        _model = YOLO(str(weights))

        if settings.mc_dropout_enabled:
            # warmup: prvý predict spustí fuse() (zlúčenie Conv+BN) — injekcia AŽ PO ňom,
            # inak fuse nahradí zbalené conv moduly (wrapper by rozbil fuse)
            import numpy as _np
            _model.predict(_np.zeros((64, 64, 3), dtype=_np.uint8), imgsz=64, device="cpu", verbose=False)
            _inject_mc_dropout(_model.model, settings.mc_dropout_rate)
    return _model


def _apply_tta_augmentations(image: np.ndarray, augmentations: int) -> list[tuple[np.ndarray, dict]]:
    """TTA augmentácie — ANATOMICKY validné pre panoramatickú RTG.

    Pôvodná verzia obsahovala vertikálny flip a ±90° rotácie (zuby hore nohami)
    → falošné nálezy; navyše _transform_bbox mal pre rotácie prehodené osi.
    Nová množina: originál, horizontálny flip, škála 0.9, škála 1.1, CLAHE.
    """
    h, w = image.shape[:2]
    results = [(image, {"flip_h": False, "flip_v": False, "rotate": 0, "scale": 1.0})]

    if augmentations <= 1:
        return results

    # 2: horizontálny flip (zrkadlenie je anatomicky ok)
    results.append((cv2.flip(image, 1), {"flip_h": True, "flip_v": False, "rotate": 0, "scale": 1.0}))

    if augmentations > 2:
        # 3: škála 0.9 (zmenšené + reflect padding)
        scale = 0.9
        new_w, new_h = int(w * scale), int(h * scale)
        scaled = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        padded = cv2.copyMakeBorder(scaled, 0, h - new_h, 0, w - new_w, cv2.BORDER_REFLECT_101)
        results.append((padded, {"flip_h": False, "flip_v": False, "rotate": 0, "scale": 0.9}))

    if augmentations > 3:
        # 4: škála 1.1 (zväčšené + orez z ľavého horného rohu)
        scale = 1.1
        new_w, new_h = int(w * scale), int(h * scale)
        scaled = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        cropped = scaled[:h, :w]
        results.append((cropped, {"flip_h": False, "flip_v": False, "rotate": 0, "scale": 1.1}))

    if augmentations > 4:
        # 5: CLAHE (kontrast — istota pri malých kazoch)
        results.append((apply_clahe(image), {"flip_h": False, "flip_v": False, "rotate": 0, "scale": 1.0}))

    return results[:augmentations]


def _transform_bbox(bbox: list[float], transform: dict, orig_w: int, orig_h: int) -> list[float]:
    """Transform bbox z koordinátov augmentovanej snímky späť do originálu."""
    x1, y1, x2, y2 = (float(v) for v in bbox)
    flip_h = transform["flip_h"]
    flip_v = transform["flip_v"]
    rotate = transform["rotate"]
    scale = transform["scale"]

    if flip_h:
        x1, x2 = orig_w - x2, orig_w - x1
    if flip_v:
        y1, y2 = orig_h - y2, orig_h - y1

    if rotate == 90:
        # 90° CW: x_rot = orig_h - y, y_rot = x  →  inverz: x = y_rot, y = orig_h - x_rot
        x1, y1, x2, y2 = y1, orig_h - x2, y2, orig_h - x1
    elif rotate == -90:
        # 90° CCW: x_rot = y, y_rot = orig_w - x  →  inverz: x = orig_w - y_rot, y = x_rot
        x1, y1, x2, y2 = orig_w - y2, x1, orig_w - y1, x2

    if scale != 1.0:
        x1, x2 = x1 / scale, x2 / scale
        y1, y2 = y1 / scale, y2 / scale

    # symetrický clamp — asymetrický by pri x2 < 0 nechal zápornú šírku
    x1, x2 = sorted((max(0.0, min(float(orig_w), x1)), max(0.0, min(float(orig_w), x2))))
    y1, y2 = sorted((max(0.0, min(float(orig_h), y1)), max(0.0, min(float(orig_h), y2))))

    return [x1, y1, x2, y2]


def _run_mc_dropout(model, image_path: str, threshold: float, passes: int) -> list[dict]:
    """MC Dropout — viacero priechodov s aktívnym dropoutom; neistota = std confidence.

    dropout sa zapína LEN na MCDropoutWrapper vrstvách (BN zostáva v eval — neposúva
    štatistiky); párovanie nálezov cez IoU, nie presný bbox (ten dá std=0 aj pri variabilite).
    """
    target = model.predictor.model.model if (hasattr(model, "predictor") and model.predictor) else model.model
    wrappers = [m for m in target.modules() if isinstance(m, MCDropoutWrapper)]
    if not wrappers:
        # predict beží cez AutoBackend kópiu modelu (nie model.model!) — injekcia tam
        _inject_mc_dropout(target, settings.mc_dropout_rate)
        wrappers = [m for m in target.modules() if isinstance(m, MCDropoutWrapper)]
    if not wrappers:
        return []

    all_findings = []
    try:
        for _ in range(passes):
            for m in wrappers:
                m.train()
            with torch.no_grad():
                results = model.predict(
                    image_path,
                    conf=threshold,
                    imgsz=1280,
                    device="cpu",
                    verbose=False,
                )
                all_findings.append(_extract_findings(results, model))
    finally:
        # dropout musí vždy skončiť — inak by ďalšie predikcie počítali s aktívnym dropoutom
        for m in wrappers:
            m.eval()

    if not all_findings:
        return []

    # párovanie nálezov cez IoU >= 0.5 per trieda
    clusters = []
    for findings in all_findings:
        for f in findings:
            placed = False
            for cl in clusters:
                if cl["label"] == f["label"] and _iou(cl["bbox"], f["bbox"]) >= 0.5:
                    cl["confs"].append(f["confidence"])
                    placed = True
                    break
            if not placed:
                clusters.append({"label": f["label"], "bbox": f["bbox"], "confs": [f["confidence"]]})

    merged = []
    for cl in clusters:
        confs = cl["confs"]
        merged.append({
            "label": cl["label"],
            "confidence": round(float(np.mean(confs)), 3),
            "bbox": cl["bbox"],
            "uncertainty": round(float(np.std(confs)), 3),
        })
    return _nms_per_class(merged, iou_threshold=0.5)



def _extract_findings(results, model, classes_sk=None) -> list[dict]:
    mapping = classes_sk or CLASSES_SK
    findings = []
    for r in results:
        h, w = r.orig_shape
        for box in r.boxes:
            label = model.names[int(box.cls)]
            sk, severity, _ = mapping.get(label, (label, "watch", "⚪"))
            x1, y1, x2, y2 = (round(v) for v in box.xyxy[0].tolist())
            findings.append(
                {
                    "label": label,
                    "label_sk": sk,
                    "severity": severity,
                    "confidence": round(float(box.conf), 3),
                    "bbox": [x1, y1, x2, y2],
                    "tooth": _tooth_number((x1 + x2) / 2, (y1 + y2) / 2, w, h),
                    "uncertainty": 0.0,
                }
            )
    return findings


def _tooth_number(cx: float, cy: float, w: float, h: float) -> int:
    """Približné FDI číslo zuba z pozície bboxu na panoramatickej RTG.

    Panorama: pravá strana pacienta je vľavo na snímke; horná/dolná arc
    podľa vertikálnej polohy stredu bboxu.
    """
    idx = min(15, int((cx / w) * 16))
    upper = cy < h / 2
    if upper:
        return 18 - idx if idx < 8 else 21 + (idx - 8)
    return 48 - idx if idx < 8 else 31 + (idx - 8)


def analyze_image(image_path: str, conf: float | None = None) -> list[dict]:
    """Vráti zoznam nálezov: label_sk, label, confidence, bbox, severity, uncertainty."""
    model = load_model()
    threshold = conf or settings.conf_threshold

    if settings.tta_enabled:
        return _analyze_image_tta(image_path, model, threshold)
    
    results_orig = model.predict(
        image_path,
        conf=threshold,
        imgsz=1280,
        device="cpu",
        verbose=False,
    )
    findings_orig = _extract_findings(results_orig, model)

    image_bgr = cv2.imread(image_path)
    if image_bgr is None:
        return findings_orig
    clahe_img = apply_clahe(image_bgr)

    tmp_dir = Path("data/tmp")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".png", dir=tmp_dir, delete=False) as tmp:
        cv2.imwrite(tmp.name, clahe_img)
        tmp_path = tmp.name

    try:
        results_clahe = model.predict(
            tmp_path,
            conf=threshold,
            imgsz=1280,
            device="cpu",
            verbose=False,
        )
        findings_clahe = _extract_findings(results_clahe, model)
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except OSError:
            pass

    merged = findings_orig.copy()
    for f_clahe in findings_clahe:
        duplicate = False
        for f_orig in findings_orig:
            if f_orig["label"] == f_clahe["label"] and _iou(f_orig["bbox"], f_clahe["bbox"]) >= 0.55:
                duplicate = True
                break
        if not duplicate:
            merged.append(f_clahe)

    try:
        m5 = load_model_mega5()
        r5 = m5.predict(image_path, conf=threshold, imgsz=640, device="cpu", verbose=False)
        for f5 in _extract_findings(r5, m5, MEGA5_CLASSES_SK):
            if f5["label"] in ("Caries", "Crown"):
                continue
            merged.append(f5)
    except FileNotFoundError:
        pass

    if settings.mc_dropout_enabled:
        mc_findings = _run_mc_dropout(model, image_path, threshold, settings.mc_dropout_passes)
        # neistota cez IoU párovanie — presný bbox z MC prechodov sa s fúzovaným
        # výsledkom takmer nikdy nezhoduje (inak neistota ostane 0.0)
        for f in merged:
            best_u = None
            for mf in mc_findings:
                if mf["label"] == f["label"] and _iou(f["bbox"], mf["bbox"]) >= 0.5:
                    if best_u is None or mf["uncertainty"] > best_u:
                        best_u = mf["uncertainty"]
            if best_u is not None:
                f["uncertainty"] = best_u

    merged.sort(key=lambda f: f["confidence"], reverse=True)
    return merged


def _analyze_image_tta(image_path: str, model, threshold: float) -> list[dict]:
    """Run TTA inference with multiple augmentations and fuse results."""
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Cannot read image: {image_path}")
    
    h, w = image.shape[:2]
    augmentations = _apply_tta_augmentations(image, settings.tta_augmentations)
    
    all_detections = []
    
    for aug_img, transform in augmentations:
        tmp_dir = Path("data/tmp")
        tmp_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(suffix=".png", dir=tmp_dir, delete=False) as tmp:
            cv2.imwrite(tmp.name, aug_img)
            tmp_path = tmp.name
        
        try:
            results = model.predict(
                tmp_path,
                conf=threshold,
                imgsz=1280,
                device="cpu",
                verbose=False,
            )
            
            for r in results:
                for box in r.boxes:
                    label = model.names[int(box.cls)]
                    sk, severity, _ = CLASSES_SK.get(label, (label, "watch", "⚪"))
                    
                    tx1, ty1, tx2, ty2 = (float(v) for v in box.xyxy[0].tolist())
                    bbox = _transform_bbox([tx1, ty1, tx2, ty2], transform, w, h)
                    
                    if bbox[2] - bbox[0] < 2 or bbox[3] - bbox[1] < 2:
                        continue
                    
                    all_detections.append({
                        "label": label,
                        "label_sk": sk,
                        "severity": severity,
                        "confidence": round(float(box.conf), 3),
                        "bbox": [round(bbox[0]), round(bbox[1]), round(bbox[2]), round(bbox[3])],
                        "tooth": _tooth_number((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2, w, h),
                        "uncertainty": 0.0,
                    })
        finally:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except OSError:
                pass
    
    fused = _weighted_box_fusion(all_detections, iou_threshold=0.55)
    final = _nms_per_class(fused, iou_threshold=0.5)
    
    try:
        m5 = load_model_mega5()
        r5 = m5.predict(image_path, conf=threshold, imgsz=640, device="cpu", verbose=False)
        for f5 in _extract_findings(r5, m5, MEGA5_CLASSES_SK):
            if f5["label"] in ("Caries", "Crown"):
                continue
            final.append(f5)
    except FileNotFoundError:
        pass
    
    if settings.mc_dropout_enabled:
        mc_findings = _run_mc_dropout(model, image_path, threshold, settings.mc_dropout_passes)
        # neistota cez IoU párovanie — presný bbox z MC prechodov sa s fúzovaným
        # výsledkom takmer nikdy nezhoduje (inak neistota ostane 0.0)
        for f in final:
            best_u = None
            for mf in mc_findings:
                if mf["label"] == f["label"] and _iou(f["bbox"], mf["bbox"]) >= 0.5:
                    if best_u is None or mf["uncertainty"] > best_u:
                        best_u = mf["uncertainty"]
            if best_u is not None:
                f["uncertainty"] = best_u
    
    final.sort(key=lambda f: f["confidence"], reverse=True)
    return final


class DentalDetector:
    """Kompatibilita pre staré eval skripty (evaluate_tta*.py) — trieda bola nahradená funkciami."""

    def __init__(self, weights_path: str = "", conf_threshold: float | None = None):
        self._conf = conf_threshold

    def analyze_image(self, image_path: str, conf: float | None = None) -> dict:
        """Staré API: vracia dict s count/findings (nové API: analyze_image() vracia list)."""
        findings = analyze_image(image_path, conf=conf or self._conf)
        return {"count": len(findings), "findings": findings}

