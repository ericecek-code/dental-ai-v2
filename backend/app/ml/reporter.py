"""Generátor pacientskeho PDF reportu (ReportLab, A4, jedna strana, slovenčina)."""

from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

PAGE_W, PAGE_H = A4
MARGIN = 1.5 * cm

SEVERITY_ORDER = {"urgent": 0, "treat_soon": 1, "watch": 2}
SEVERITY_COLORS = {
    "urgent": HexColor("#ef4444"),
    "treat_soon": HexColor("#f59e0b"),
    "watch": HexColor("#38bdf8"),
}
SEVERITY_LABELS = {
    "urgent": "Naliehavé",
    "treat_soon": "Vybavte čoskoro",
    "watch": "Sledujte",
}

FONTS_DIR = Path(__file__).resolve().parent / "fonts"
FONT_CANDIDATES = [
    # 1) bundle v projekte (funguje všade — aj v Linux kontajneri)
    ("DejaVuSans", FONTS_DIR / "DejaVuSans.ttf"),
    ("DejaVuSans-Bold", FONTS_DIR / "DejaVuSans-Bold.ttf"),
    # 2) systémové DejaVu (Linux: fonts-dejavu-core)
    ("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ("DejaVuSans-Bold", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    # 3) Windows Arial
    ("Arial", "C:/Windows/Fonts/arial.ttf"),
    ("Arial-Bold", "C:/Windows/Fonts/arialbd.ttf"),
    ("Arial-Italic", "C:/Windows/Fonts/ariali.ttf"),
    ("Arial-BoldItalic", "C:/Windows/Fonts/arialbi.ttf"),
]


def _register_fonts() -> dict[str, str]:
    """Zaregistruje TTF fonty s diakritikou; fallback na Helvetica."""
    loaded = {}
    for name, path in FONT_CANDIDATES:
        if name in loaded:
            continue
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                loaded[name] = name
            except Exception:
                pass
    normal = loaded.get("DejaVuSans") or loaded.get("Arial") or "Helvetica"
    bold = loaded.get("DejaVuSans-Bold") or loaded.get("Arial-Bold") or "Helvetica-Bold"
    italic = loaded.get("Arial-Italic", normal)
    return {"normal": normal, "bold": bold, "italic": italic}


def generate_patient_report(out_path: str, filename: str, findings: list[dict],
                            overlay_image_path: str | None = None) -> str:
    """Vygeneruje jednostránkový A4 PDF posudok a vráti out_path."""
    fonts = _register_fonts()
    c = canvas.Canvas(out_path, pagesize=A4)
    c.setTitle("Dental AI — posudok RTG snímky")

    y = PAGE_H - MARGIN

    c.setFont(fonts["bold"], 16)
    c.setFillColor(HexColor("#111827"))
    c.drawString(MARGIN, y, "Dental AI — posudok RTG snímky")
    y -= 14
    c.setFont(fonts["normal"], 9)
    c.setFillColor(HexColor("#6b7280"))
    datum = datetime.now().strftime("%d.%m.%Y")
    c.drawString(MARGIN, y, f"Dátum: {datum}    Súbor: {filename}")
    y -= 8
    c.setStrokeColor(HexColor("#d1d5db"))
    c.setLineWidth(0.7)
    c.line(MARGIN, y, PAGE_W - MARGIN, y)
    y -= 24

    c.setFont(fonts["bold"], 12)
    c.setFillColor(HexColor("#111827"))
    c.drawString(MARGIN, y, "Nálezy")
    y -= 20

    ordered = sorted(findings, key=lambda f: SEVERITY_ORDER.get(f.get("severity"), 9))
    for f in ordered:
        color = SEVERITY_COLORS.get(f.get("severity"), HexColor("#9ca3af"))
        c.setFillColor(color)
        c.circle(MARGIN + 4, y + 3.5, 4, stroke=0, fill=1)
        c.setFillColor(HexColor("#111827"))
        c.setFont(fonts["normal"], 11)
        c.drawString(MARGIN + 16, y, str(f.get("label_sk", "")))
        conf = float(f.get("confidence", 0.0))
        c.setFont(fonts["bold"], 11)
        c.drawRightString(PAGE_W - MARGIN, y, f"{conf * 100:.0f} %")
        y -= 18

    y -= 12

    if overlay_image_path and os.path.exists(overlay_image_path):
        try:
            img = ImageReader(overlay_image_path)
            iw, ih = img.getSize()
            max_w = 17 * cm
            max_h = 8.5 * cm
            scale = min(max_w / iw, max_h / ih)
            w, h = iw * scale, ih * scale
            x = (PAGE_W - w) / 2
            c.drawImage(img, x, y - h, width=w, height=h, mask="auto")
            y -= h + 18
        except Exception:
            pass

    c.setFont(fonts["normal"], 9)
    x = MARGIN
    for sev in ("urgent", "treat_soon", "watch"):
        c.setFillColor(SEVERITY_COLORS[sev])
        c.circle(x + 4, y + 3, 3.5, stroke=0, fill=1)
        c.setFillColor(HexColor("#6b7280"))
        label = SEVERITY_LABELS[sev]
        c.drawString(x + 12, y, label)
        x += 12 + pdfmetrics.stringWidth(label, fonts["normal"], 9) + 18

    c.setFont(fonts["italic"], 8)
    c.setFillColor(HexColor("#9ca3af"))
    disclaimer = "AI je asistent, nie diagnóza. Klinické rozhodnutie vždy patrí lekárovi."
    c.drawCentredString(PAGE_W / 2, MARGIN, disclaimer)

    c.showPage()
    c.save()
    return out_path
