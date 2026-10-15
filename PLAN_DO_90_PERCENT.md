# PLÁN: Dental AI v2 → 90 % komerčnej špičky (špičková analýza, 2026-10-10)

*STAV: NÁVRH schválený na zápis — NIČ neaplikované. Zdroje: C: datasety + free Kaggle (D:/E: vynechané na výslovné želanie).*

---

## VÝCHODISKOVÝ STAV (v2, commit 0f6abc7, LIVE na HF)

- Kaz (panoramic): recall **72,3 %**, mAP50 **61,0 %** · Plomba **92 %** · Impacted 85,8 % · Deep Caries 53,1 % · Periapical 48,0 %
- Funkcie: duálny model, TTA, MC Dropout neistota, Grad-CAM, odontogram (hrubý FDI), PDF SK, login, feedback loop
- Funkčná parita s komerčnou špičkou (Overjet/Pearl/Denti.AI/VideaHealth): **~55–60 %**

## GAP vs KOMERČNÁ ŠPIČKA

1. Bone loss (parodontóza) — chýba celá schopnosť
2. Kameň (calculus) — chýba
3. Bitewing + periapikálne views — chýbajú (len panoramic)
4. DICOM input — chýba
5. Presné FDI číslovanie — len hrubý grid
6. Presnosť kaz −10–18 pp, deep caries/periapical −25–35 pp
7. Neistota + feedback loop + cena 0 € — **v2 vedie** (diferenčiácia)

## DÁTA (C: + Kaggle free)

**Máme na C:** DENTEX 10,9 GB (kanon), mega-dataset 7 228 snímok, dentex_night 3,8 GB, restorative-ai, Dental-X-ray-1, combined v1/v2, kernel_outputy.
**Stiahnuť (Kaggle, ~5,3 GB, na C: — 137 GB voľných):**
- P0: `lokisilvres/dental-disease-panoramic-detection` (2 429 MB) · `christopherhuang88/dentex-quadrant-enumeration-diseas` (2 050 MB, tooth-level FDI) · `muhammadsajad/periapical-xrays` (153 MB) · `muhammadsajad/unlabeled-periapical-xrays` (2 451 MB, pseudolabeling) · `shubhamskg/bitewing-datasets` (220 MB)
- P1: dental-opg-xray (197 MB) · tooth-number01 (1 406 MB) · childrens-panoramic (1 583 MB)
**Roboflow:** kľúč doplniť do .env (ROBOFLOW_API_KEY) — Universe YOLO exporty.

## PLÁN PODĽA FÁZ

### FÁZA 0 — DÁTA (týždeň; +5–15 pp)
- N0.1 Stiahnuť 5×P0 na `C:\Users\PC1\Desktop\dental-ai\archive\` (junction z v2)
- N0.2 Pseudolabeling/cross-labeling: mega (7 228) + unlabeled periapical označkovať nočným v8s → len zhody (~7 000+ čistých kazov)
- N0.3 Jednotný merge do DENTEX konvencií (poučenie z 3 zlyhaných experimentov: nemiešať značky priamo)

### FÁZA 1 — MODEL (+10–20 pp; 2–3 týždne; Kaggle ~18 h: 10/5/3 h)
- N1.1 Retrén YOLOv11s (alebo v26-s) na merged čistých dátach
- N1.2 Bitewing model (separátna doména → cieľ 85–95 %)
- N1.3 Periapikálny model (nové views/triedy)
- N1.4 Bone loss + calculus modul (nová schopnosť)
- N1.5 FDI 3-fázový pipeline (kvadrant → zub → diagnóza; DENTEX-QED + tooth-number01)

### FÁZA 2 — APLIKÁCIA (funkčná parita ~90 %)
- N2.1 DICOM input (pydicom + windowing)
- N2.2 VLM druhý názor — port gemini_vision.py z HF Space histórie (YOLO vs Gemini side-by-side)
- N2.3 eval/scorer.py port (mAP validácia pred/po pri každom retréne)
- N2.4 Charting v2: per-tooth diagnózy + WebSocket progres
- N2.5 Treatment suggestions (rule-based, framing „druhý pohľad")
- N2.6 Report v2: per-tooth tabuľka + neistota + VLM zhrnutie

### FÁZA 3 — INFRA
- N3.1 ONNX export (2–5× rýchlejšia CPU inferencia)
- N3.2 Space secrets údržba + ROBOFLOW_API_KEY + cron ping proti sleep

## CESTA K 90 %

| Krok | Kaz recall (panoramic) | Parita |
|---|---|---|
| dnes | 72,3 % | ~55–60 % |
| +Fáza 0 | ~78 % | ~65 % |
| +Fáza 1 | ~80–85 % | ~85 % |
| +Fáza 2 | — | **~90 %** |

Nerezalieme: FDA/CE, efekt miliónov snímok (mimo dema).

## ZÁVISLOSTI A RIZIKÁ

- Kaggle kvóta ~18 h GPU → rozdeliť 10 (hlavný retrén) / 5 (BW) / 3 (PA); lokálna 1080 Ti ako fallback
- Pseudolabeling závisí od kvality nočného modelu → prah conf ≥ 0.5 + IoU zhoda oboch smerov
- NIKDY nemiešať externé značkové konvencie s DENTEX priamo (3 potvrdené experimenty)
- VLM port potrebuje GEMINI_API_KEY v Space secrets

## ČO POTREBUJEM OD POUŽÍVATEĽA

1. Zelená na Fázu 0 (sťahovanie ~5,3 GB na C: + pseudolabeling)
2. Voliteľne: ROBOFLOW_API_KEY, GEMINI_API_KEY
3. Potvrdenie rozdelenia Kaggle kvóty
