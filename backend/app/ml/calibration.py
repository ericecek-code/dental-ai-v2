"""Confidence calibration — Temperature Scaling for reliable probabilities.

YOLO confidence scores are overconfident; calibration maps them to true probabilities.
Based on Guo et al. "On Calibration of Modern Neural Networks" (ICML 2017).
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Literal

import numpy as np

CALIBRATION_PATH = Path("backend/weights/calibration.json")


class TemperatureScaler:
    """Temperature scaling: p_cal = sigmoid(logit / T).

    T > 1 softens probabilities (reduces overconfidence).
    T = 1 is identity.
    """

    def __init__(self, temperature: float = 1.0):
        self.temperature = max(0.01, temperature)

    @classmethod
    def fit(cls, logits: np.ndarray, labels: np.ndarray) -> "TemperatureScaler":
        """Find optimal temperature by minimizing NLL on validation set.

        Args:
            logits: (N,) raw model logits (pre-sigmoid)
            labels: (N,) binary labels (0/1)

        Returns:
            Fitted TemperatureScaler
        """
        from scipy.optimize import minimize_scalar

        def nll(t: float) -> float:
            if t <= 0:
                return 1e9
            probs = 1.0 / (1.0 + np.exp(-logits / t))
            probs = np.clip(probs, 1e-7, 1 - 1e-7)
            return -np.mean(labels * np.log(probs) + (1 - labels) * np.log(1 - probs))

        result = minimize_scalar(nll, bounds=(0.05, 10.0), method="bounded")
        return cls(result.x)

    def calibrate(self, confidence: float) -> float:
        """Calibrate a confidence score (already sigmoid output).

        Args:
            confidence: model output in [0, 1]

        Returns:
            Calibrated probability
        """
        # Convert back to logit, scale, convert back
        eps = 1e-7
        conf = np.clip(confidence, eps, 1 - eps)
        logit = math.log(conf / (1 - conf))
        calibrated_logit = logit / self.temperature
        return 1.0 / (1.0 + math.exp(-calibrated_logit))

    def calibrate_batch(self, confidences: list[float]) -> list[float]:
        return [self.calibrate(c) for c in confidences]

    def save(self, path: Path = CALIBRATION_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"temperature": self.temperature}), encoding="utf-8")

    @classmethod
    def load(cls, path: Path = CALIBRATION_PATH) -> "TemperatureScaler":
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls(data.get("temperature", 1.0))
        return cls(1.0)


# Per-class temperatures (different classes may need different calibration)
CLASS_TEMPERATURES = {
    "Caries": 1.0,
    "Deep Caries": 1.0,
    "Periapical Lesion": 1.0,
    "Impacted": 1.0,
}


def calibrate_findings(findings: list[dict]) -> list[dict]:
    """Apply per-class temperature scaling to findings."""
    calibrated = []
    for f in findings:
        label = f.get("label", "")
        temp = CLASS_TEMPERATURES.get(label, 1.0)
        if temp != 1.0:
            scaler = TemperatureScaler(temp)
            f = {**f, "confidence": round(scaler.calibrate(f["confidence"]), 3)}
        calibrated.append(f)
    return calibrated


def collect_calibration_data(
    val_image_paths: list[str],
    val_annotations: list[list[dict]],
    conf_threshold: float = 0.01,
) -> tuple[np.ndarray, np.ndarray]:
    """Collect logits and labels from validation set for calibration.

    Args:
        val_image_paths: list of image paths
        val_annotations: list of ground truth annotations per image
        conf_threshold: very low threshold to get all predictions

    Returns:
        (logits, labels) arrays for temperature fitting
    """
    from app.ml.detector import load_model, _iou

    model = load_model()
    all_logits = []
    all_labels = []

    for img_path, gts in zip(val_image_paths, val_annotations):
        results = model.predict(img_path, conf=conf_threshold, imgsz=1280, device="cpu", verbose=False)

        for r in results:
            h, w = r.orig_shape
            for box in r.boxes:
                label = model.names[int(box.cls)]
                conf = float(box.conf)
                x1, y1, x2, y2 = box.xyxy[0].tolist()

                # Match with GT
                matched = False
                for gt in gts:
                    if gt["label"] == label and _iou([x1, y1, x2, y2], gt["bbox"]) >= 0.5:
                        matched = True
                        break

                # Convert confidence to logit
                eps = 1e-7
                conf_clipped = np.clip(conf, eps, 1 - eps)
                logit = math.log(conf_clipped / (1 - conf_clipped))

                all_logits.append(logit)
                all_labels.append(1.0 if matched else 0.0)

    return np.array(all_logits), np.array(all_labels)


def compute_ece(confidences: np.ndarray, labels: np.ndarray, n_bins: int = 10) -> float:
    """Expected Calibration Error (ECE) — lower is better."""
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    bin_lowers = bin_boundaries[:-1]
    bin_uppers = bin_boundaries[1:]

    ece = 0.0
    for bin_lower, bin_upper in zip(bin_lowers, bin_uppers):
        in_bin = (confidences > bin_lower) & (confidences <= bin_upper)
        prop_in_bin = in_bin.mean()
        if prop_in_bin > 0:
            accuracy_in_bin = labels[in_bin].mean()
            avg_confidence_in_bin = confidences[in_bin].mean()
            ece += np.abs(avg_confidence_in_bin - accuracy_in_bin) * prop_in_bin
    return ece