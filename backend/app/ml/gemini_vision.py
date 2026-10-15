"""Gemini Vision — AI druhý názor na RTG snímku (VLM, nezávislý od YOLO).

Port z HF Space histórie (júl 2026) — adaptované na v2: API kľúč zo settings
(GEMINI_API_KEY), žiadny hardcoded secret. Vráti nálezy + súhrn + match s YOLO.
"""

import base64
import json
import logging
import re
import time
from typing import Any, Dict, List

import cv2
import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-2.5-flash"          # konkrétny model — rolling "latest" alias padá na kvóty/404
DEFAULT_FALLBACK = "gemini-2.5-flash-lite"  # záložný model, keď primárny vráti 429/404


def _model_chain() -> List[str]:
    """Primárny model + záložné modely z konfigurácie (bez duplikátov, v poradí)."""
    primary = (getattr(settings, "gemini_model", "") or DEFAULT_MODEL).strip()
    raw = getattr(settings, "gemini_fallback_models", "") or DEFAULT_FALLBACK
    chain: List[str] = []
    for name in [primary, *raw.split(",")]:
        name = name.strip()
        if name and name not in chain:
            chain.append(name)
    return chain


def _short_api_error(response) -> str:
    """Krátky a čitateľný dôvod z odpovede Google API (kvóta, neplatný model…)."""
    try:
        payload = response.json() or {}
        msg = str((payload.get("error") or {}).get("message", "")).replace("\n", " ")
        msg = " ".join(msg.split())
        if msg:
            return f"HTTP {response.status_code} — {msg[:220]}"
    except Exception:  # noqa: BLE001
        pass
    return f"HTTP {response.status_code} — {response.text[:220]}"

DENTAL_PROMPT = """Si skúsený stomatológ. Analyzuj túto zubnú RTG snímku.

Identifikuj KAŽDÝ nález a urči číslo zuba podľa FDI notácie (ak je to možné):
- 1. kvadrant (horná pravá): zuby 11-18
- 2. kvadrant (horná ľavá): zuby 21-28
- 3. kvadrant (dolná ľavá): zuby 31-38
- 4. kvadrant (dolná pravá): zuby 41-48
Ak snímka nezobrazuje celú čeľusť (bitewing/periapikálna), číslo zuba odhadni
a pridaj k description poznámku "(orientačné)".

Pre každý nález uveď:
- label: typ nálezu (presne ako: Caries, Filling, Crown, Implant, Root Canal Treatment, Missing teeth, Periapical lesion, Retained root, Root Piece, Impacted tooth, Cyst, Bone loss)
- tooth: FDI číslo zuba (napr. "36") alebo "" ak neurčiteľné
- quadrant: číslo kvadrantu (1-4) alebo 0
- confidence: 0.0-1.0
- severity: urgent / treat_soon / watch
- description: krátky popis v Slovenčine

VRÁŤ IBA TOTO JSON (bez ďalšieho textu):
{
  "findings": [
    {
      "label": "Caries",
      "tooth": "36",
      "quadrant": 3,
      "confidence": 0.85,
      "severity": "treat_soon",
      "description": "Stredný kaz na distálnej strane"
    }
  ],
  "overall_assessment": "Súhrnný posudok v Slovenčine"
}"""

BACKTICK_CODE_BLOCK = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
JSON_FIELD_TYPE = re.compile(r'"label"\s*:\s*"([^"]+)"')


def image_to_base64_jpeg(image_bgr, quality=85) -> str:
    ok, buf = cv2.imencode(".jpg", image_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError("Nepodarilo sa zakódovať snímku do JPEG")
    return base64.b64encode(buf).decode("utf-8")


def _parse_findings(parsed: dict) -> tuple[List[Dict], str]:
    findings = []
    for f in parsed.get("findings", []):
        tooth = str(f.get("tooth", "") or "")
        findings.append({
            "label": f.get("label", "Unknown"),
            "tooth": tooth,
            "quadrant": int(f.get("quadrant", 0) or 0),
            "confidence": float(f.get("confidence", 0.5) or 0.5),
            "severity": f.get("severity", "watch"),
            "description": f.get("description", ""),
            "bbox": None,
            "location": f"zub {tooth}" if tooth else "neurčené",
        })
    return findings, parsed.get("overall_assessment", "")


def _extract_findings_from_json(json_str: str) -> tuple[List[Dict], str]:
    try:
        return _parse_findings(json.loads(json_str))
    except json.JSONDecodeError:
        pass
    # oprava prerušeného JSON
    try:
        fixed = json_str.rstrip().rstrip(",")
        fixed += "]" * (fixed.count("[") - fixed.count("]"))
        fixed += "}" * (fixed.count("{") - fixed.count("}"))
        return _parse_findings(json.loads(fixed))
    except Exception:
        return [], ""


def parse_gemini_response(response_text: str) -> Dict[str, Any]:
    m = BACKTICK_CODE_BLOCK.search(response_text)
    if m:
        findings, overall = _extract_findings_from_json(m.group(1))
        if findings:
            return {"findings": findings, "overall_assessment": overall}
    i, j = response_text.find("{"), response_text.rfind("}")
    if i != -1 and j > i:
        findings, overall = _extract_findings_from_json(response_text[i:j + 1])
        if findings:
            return {"findings": findings, "overall_assessment": overall}
    # posledná možnosť: regex ťahanie polí
    findings = []
    for m in JSON_FIELD_TYPE.finditer(response_text):
        rest = response_text[m.start():m.start() + 500]
        tooth_m = re.search(r'"tooth"\s*:\s*"([^"]+)"', rest)
        conf_m = re.search(r'"confidence"\s*:\s*([\d.]+)', rest)
        sev_m = re.search(r'"severity"\s*:\s*"([^"]+)"', rest)
        desc_m = re.search(r'"description"\s*:\s*"([^"]+)"', rest)
        findings.append({
            "label": m.group(1),
            "tooth": tooth_m.group(1) if tooth_m else "",
            "quadrant": 0,
            "confidence": float(conf_m.group(1)) if conf_m else 0.5,
            "severity": sev_m.group(1) if sev_m else "watch",
            "description": desc_m.group(1) if desc_m else "",
            "bbox": None,
            "location": "Unknown",
        })
    return {"findings": findings, "overall_assessment": response_text[:500] if response_text else "Bez posudku"}


def analyze_xray_with_gemini(image_bgr, custom_prompt=None, temperature=0.3, max_retries=3) -> Dict[str, Any]:
    """Zavolá Gemini Flash s base64 snímkou; vráti findings + overall_assessment."""
    started = time.time()
    api_key = (getattr(settings, "gemini_api_key", "") or "").strip()
    if not api_key:
        return {"gemini_detections": [], "gemini_raw_text": "", "overall_assessment": "",
                "success": False, "error": "GEMINI_API_KEY nie je nastavený (Space secrets / .env).",
                "processing_time_ms": 0}

    b64 = image_to_base64_jpeg(image_bgr)
    payload = {
        "contents": [{
            "parts": [
                {"text": custom_prompt or DENTAL_PROMPT},
                {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
            ]
        }],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": 4096},
    }
    errors: List[str] = []
    for model in _model_chain():
        for attempt in range(max_retries):
            try:
                r = requests.post(
                    f"{GEMINI_API_BASE}/{model}:generateContent",
                    headers={"x-goog-api-key": api_key},
                    json=payload, timeout=90,
                )
                # 429 (kvóta) a 404 (zrušený model) skúsime prekonať ďalším modelom z reťazca
                if r.status_code in (429, 404, 503):
                    errors.append(f"{model}: {_short_api_error(r)}")
                    if r.status_code == 429:
                        time.sleep(1.5 * (attempt + 1))
                        continue
                    break
                r.raise_for_status()
                data = r.json()
                text = "".join(
                    p.get("text", "") for c in data.get("candidates", [])
                    for p in c.get("content", {}).get("parts", [])
                )
                parsed = parse_gemini_response(text)
                if not parsed["findings"] and not parsed["overall_assessment"]:
                    errors.append(f"{model}: prázdna odpoveď modelu")
                    break
                return {
                    "gemini_detections": parsed["findings"],
                    "gemini_raw_text": text[:2000],
                    "overall_assessment": parsed["overall_assessment"],
                    "success": True,
                    "error": None,
                    "model": model,
                    "processing_time_ms": int((time.time() - started) * 1000),
                }
            except Exception as e:
                errors.append(f"{model}: {e}")
                time.sleep(1)
    unique = list(dict.fromkeys(errors))
    return {"gemini_detections": [], "gemini_raw_text": "", "overall_assessment": "",
            "success": False, "error": "Gemini volanie zlyhalo: " + " | ".join(unique[:3]),
            "model": None,
            "processing_time_ms": int((time.time() - started) * 1000)}


_LABEL_MAP = {
    "kaz": "caries", "deep caries": "caries", "hlboký kaz": "deep caries",
    "plomba": "filling", "korunka": "crown", "implantát": "implant",
    "endodoncia": "root canal treatment", "periapikálna lézia": "periapical lesion",
    "chýbajúci zub": "missing teeth", "retinovaný zub": "impacted tooth",
    "retinovaný koreň": "retained root", "koreňový fragment": "root piece",
    "impacted": "impacted tooth", "periapical lesion": "periapical lesion",
    "root canal treatment": "root canal treatment", "missing teeth": "missing teeth",
    "retained root": "retained root", "root piece": "root piece", "cyst": "cyst",
    "bone loss": "bone loss", "caries": "caries", "filling": "filling",
    "crown": "crown", "implant": "implant",
}


def _norm_label(label: str) -> str:
    l = (label or "").strip().lower()
    return _LABEL_MAP.get(l, l)


def _tooth_of(det: Dict) -> str:
    t = str(det.get("tooth", "") or "").strip()
    if t:
        return t
    m = re.search(r"(\d{2})", str(det.get("location", "")))
    return m.group(1) if m else ""


_RESTORATION_LABELS = {
    "filling", "crown", "implant", "root canal treatment",
}
_PATHOLOGY_LABELS = {
    "caries", "deep caries", "periapical lesion", "cyst", "bone loss",
    "impacted tooth", "retained root", "root piece", "missing teeth",
}


def _label_group(label: str) -> str:
    """Skupina nálezu — slovníky modelov sa líšia (Filling vs Crown), skupina nie."""
    norm = _norm_label(label)
    if norm in _RESTORATION_LABELS:
        return "restoration"
    if norm in _PATHOLOGY_LABELS:
        return "pathology"
    return norm or "other"


def attach_tooth_bbox_estimates(detections: List[Dict], image_shape: tuple[int, int]) -> List[Dict]:
    """Doplní orientačný rámček k nálezom, ktoré majú číslo zuba (odhad z FDI na panoráme).

    Gemini nevracia súradnice — poloha sa odhaduje z čísla zuba, preto sú rámčeky
    v UI výslovne označené ako orientačné.
    """
    try:
        from app.ml.anatomical import estimate_tooth_rect
    except Exception:  # noqa: BLE001
        return detections
    for det in detections:
        det.setdefault("bbox_estimate", None)
        det.setdefault("bbox_estimate_source", None)
        tooth = _tooth_of(det)
        if tooth.isdigit():
            rect = estimate_tooth_rect(image_shape, int(tooth))
            if rect:
                det["bbox_estimate"] = [int(v) for v in rect]
                det["bbox_estimate_source"] = "fdi_estimate"
    return detections


def match_yolo_gemini(yolo_detections: List[Dict], gemini_detections: List[Dict]) -> Dict[str, Any]:
    """Párovanie YOLO × Gemini podľa (normalizovaný label, číslo zuba)."""
    matched, yolo_only, gemini_only = [], [], []
    used = [False] * len(gemini_detections)
    for yolo in yolo_detections:
        y_label, y_tooth = _norm_label(yolo.get("label", "")), _tooth_of(yolo)
        hit = None
        for i, gem in enumerate(gemini_detections):
            if used[i]:
                continue
            g_label, g_tooth = _norm_label(gem.get("label", "")), _tooth_of(gem)
            tooth_ok = (not y_tooth) or (not g_tooth) or y_tooth == g_tooth
            same_exact = y_label == g_label
            # zhoda názvu stačí vždy; rozdielne názvy (Filling vs Crown) uznáme,
            # len ak ide o tú istú skupinu A oba modely uviedli to isté číslo zuba
            same_group = _label_group(yolo.get("label", "")) == _label_group(gem.get("label", ""))
            if tooth_ok and (same_exact or (same_group and y_tooth and g_tooth)):
                hit = i
                break
        if hit is not None:
            used[hit] = True
            gem = gemini_detections[hit]
            matched.append({
                "label": yolo.get("label", ""),
                "tooth": y_tooth or _tooth_of(gem),
                "yolo_confidence": yolo.get("confidence", 0),
                "gemini_confidence": gem.get("confidence", 0),
                "severity": yolo.get("severity", gem.get("severity", "watch")),
                "description_gemini": gem.get("description", ""),
                "bbox_estimate": gem.get("bbox_estimate"),
            })
        else:
            yolo_only.append({
                "label": yolo.get("label", ""), "tooth": y_tooth,
                "confidence": yolo.get("confidence", 0),
                "severity": yolo.get("severity", "watch"),
            })
    for i, gem in enumerate(gemini_detections):
        if not used[i]:
            gemini_only.append({
                "label": gem.get("label", ""), "tooth": _tooth_of(gem),
                "confidence": gem.get("confidence", 0),
                "severity": gem.get("severity", "watch"),
                "description": gem.get("description", ""),
                "bbox_estimate": gem.get("bbox_estimate"),
            })
    return {
        "matched": matched, "yolo_only": yolo_only, "gemini_only": gemini_only,
        "summary": {
            "yolo_count": len(yolo_detections), "gemini_count": len(gemini_detections),
            "matched_count": len(matched), "yolo_only_count": len(yolo_only),
            "gemini_only_count": len(gemini_only),
        },
    }

