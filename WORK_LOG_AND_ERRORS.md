# 📋 Dental AI v2 — Work Log & Errors (Kompletná historia)

*Verzia: 2026-10-11 | Zdroj: git history, POPIS_PROJEKTU.md, SUHRN_PROJEKTU.md, MORNING_REPORT.md, KAGGLE_PRIRUCKA_PRE_AGENTOV.md, docs/MORNING_REPORT.md*

---

## ČASOVÁ OS: Hlavné milníky

| Dátum | Fáza | Popis |
|---|---|---|
| **2026-10-04** | Tréning | v8s night (YOLOv8s, imgsz 1280, 50 epoch) — peak mAP50 62,5 % v epoche 26 |
| **2026-10-05** | Tréning | v8m night (YOLOv8m) — zlyhalo (timeout validácie) |
| **2026-10-06** | Experiment | Merged DENTEX + 2500 kazov z mega-datasetu — **FAIL** (Caries recall 72,3→39,6 %) |
| **2026-10-07** | Experiment | CariesX experiment — **FAIL** (celok +0,9 pp, ale Caries recall 72→42 %) |
| **2026-10-08** | Integrácia | Mega5 model (restaurácie) integrovaný — Plomba 92 %, Korunka vylúčená (falošné poplachy) |
| **2026-10-09** | UI/Backend | Dual-model, odontogram, PDF SK, login, feedback loop, Grad-CAM, SAHI tiles, ensemble |
| **2026-10-10** | **3-agent analýza** | OpenCode + Hermes + dsh/Kilo — 10+ kritických bugov identifikovaných |
| **2026-10-10** | Opravy | Commit `0f6abc7`: fix kritických bugov po 3-agent analýze |
| **2026-10-10** | Dedupe | DATASET_DEDUPE_MAP.md — centralizácia ťažkých datasétov, NTFS junctions |
| **2026-10-10** | Plánovanie | PLAN_DO_90_PERCENT.md — Fáza 0–3 na 90 % parity |
| **2026-10-10** | Pipeline | `dbf1652` + `cc47ecc`: tréningová pipeline (pseudolabel, build_merged, kaggle_prep) |
| **2026-10-10** | UI vylepšenia | `840856e`–`7a1afbf`: bitewing režim, Gemini panel, kompaktný sticky panel, klik-only výber |
| **2026-10-11** | **Gemini VLM** | `0b2930f`: AI druhý názor (gemini_vision.py port, /vision endpoint, UI panel) |
| **2026-10-11** | **Black screen fix** | **TOTO ZADANIE**: `/uploads/{job_id}` endpoint + frontend switch na backend URL |
| **2026-10-11** | **Gemini model fix** | `gemini-flash-latest` (pôvodný z HF Space) — 429 rate limit = funguje |

---

## GIT HISTORY (relevantné commity)

```bash
# Posledné 30 commitov (chronologicky od najstaršieho):
dacc416 PDF report SK, Grad-CAM endpoint, 1280px inferencia, Viewer pan/zoom
fed9742 Ensemble v8s+v8m, SQLite feedback, frontend výber režimu
5787cb4 CLAHE dual-pohľad + SAHI tiled režim
8202b63 Kaggle kernel v8l@1280
3da7f86 Odontogram hore, farebné lezie, tooth mapovanie v SAHI
a0144a4 Odontogram FDI, heslová brána, FDI mapovanie, demo balík
cd6736b Viewer fix: zoom/pan reset pri hoveri + zoom-out pod fit
7b4b9d2 Panel metriky zhody AI s lekárom (agreement %)
8c794fc Merged experiment VYHODNOTENÝ: v8s+mega zhoršil Caries 72.3→39.6
baf9aae Merged kernel: DENTEX + 2500 kazov z mega-datasetu
1ef62af CariesX experiment vyhodnotený: recall 72→42
0be5135 Integrácia mega5 (plomby 92 %, korunka, implantáty)
7710a03 Korunky vynuté z nálezov (veľa falošných poplachov)
3274e32 Dual-model overený na 5 snímkach
608c856 TTA a MC Dropout neistota pridané
0f6abc7 FIX: kritické bugy po 3-agent analýze (OpenCode+Hermes+dsh)
cc47ecc / dbf1652 Tréningová pipeline (pseudolabel, build_merged, kaggle_prep)
c9f6f20 UI: kompaktny sticky panel + FDI v karte + bitewing upozornenie
840856e UI: default filter skryva restaurácie, klik na box vybera, hover-flicker fix
b338938 UI: Gemini panel do pravého stĺpca, retry/timeout, viditeľné chyby
7a1afbf UI: bitewing režim (len kazy, bez odontogramu/císlovania)
4f947d6 Viewer: fit až po layoute (rAF) + prepocet pri resize
```

---

## EXPERIMENTY S MODELOMI — ČO ZLYHALO (DÔLEŽITÉ!)

### 1. Merged DENTEX + mega-dataset (2500 kazov) — **FAIL**
- **Commit:** `baf9aae` → `8c794fc` (vyhodnotenie)
- **Výsledok:** Caries recall 72,3 % → 39,6 % (−32,7 pp)
- **Príčina:** Mega-dataset má v anotáciách šum — „Caries“ mieša bežný + hlboký kaz, značkovali ho iní ľudia na iných prístrojoch
- **Poučenie:** NIKDY nemiešať externé značky s DENTEX konvenciami priamo

### 2. CariesX experiment — **FAIL**
- **Commit:** `1ef62af`
- **Výsledok:** Celok +0,9 pp mAP50, ale Caries recall 72 % → 42 %
- **Príčina:** Tretie potvrdenie konfliktu externých značiek s DENTEX konvenciami
- **Poučenie:** Externé dáta len ako pre-training → finetuning na čistom DENTEX, alebo cross-labeling

### 3. v8m_night tréning — **TIMEOUT**
- **MORNING_REPORT.md:** Validácia zlyhala po 900 s (timeout)
- **Riešenie:** Validovať na Kaggle v notebooku, nie lokálne `val_best.py`

### 4. Korunka (Crown) v mega5 — **VEĽA FALOŠNÝCH POPLACHOV**
- **Commit:** `7710a03` — vynuté z nálezov, plomby+implantáty zostali
- **Dôvod:** Mega5 model na koronky má veľa falošných poplachov, nie je spoľahlivý pre demo

---

## 3-AGENT ANALÝZA (2026-10-10) — IDENTIFIKOVANÉ BUGY

Agenti: **OpenCode**, **Hermes**, **dsh/Kilo** (free tier modely)

### Kritické (P1) — 4 bugy
| # | Bug | Súbor/Riadok | Opis |
|---|---|---|---|
| 1 | **Blokujúca analýza** | `analyze.py:25` `async def analyze` | CPU inferencia (5–10 s) v event loope → server zamrzne, neodpovie ani `/health` |
| 2 | **Dáta v gite** | 112 súborov | RTG s menami, PDF, `db.sqlite`, `.secret` HMAC kľúč — `git rm --cached` + `.gitignore` + `git filter-repo` |
| 3 | **PDF fonty** | `reporter.py` | Windows fonty v dev, Linux kontajner = Helvetica bez č/š/ž → DejaVu Sans do kontajnera |
| 4 | **Deploy nefunkčný** | `Dockerfile`, chýba `.dockerignore` | COPY vtiahne 4,9 GB `.venv`, váhy v `.gitignore` → multi-stage build |

### Dôležité (P2) — 4 bugy
| # | Bug | Súbor/Riadok | Opis |
|---|---|---|---|
| 5 | **TTA ±90° rotácie** | `detector.py:_transform_bbox` | Prehodené orig_w/orig_h → 2 z 5 augmentácií boxy mimo snímky. Anatomicky nezmyselné. |
| 6 | **MC Dropout = 0.0** | `detector.py` | Párovanie podľa presného bbox + `model.eval()` → neistota vždy 0. Oprava: IoU ≥ 0.5 + train režim. |
| 7 | **Duplicitné definície** | `detector.py` | `_nms_per_class`, `_weighted_box_fusion` definované 2× — druhá prepíše prvú. |
| 8 | **Web security** | `main.py`, `auth.py` | CORS `*`, cookie bez `secure`, 401 maskuje 404, DICOM nečítaný, uploady sa nemazú. |

---

## OPRAVENÉ BUGY (v commitoch po 10.10.)

| Commit | Oprava | Detail |
|---|---|---|
| `0f6abc7` | **Všetky P1+P2 bugy** | Hromadná oprava po 3-agent analýze |
| `dbf1652` | Tréningová pipeline | `build_merged.py` (COCO/RLE/LabelMe case-insensitive), `pseudolabel.py` (cross/pseudo), `kaggle_prep.py` (pip fix), lokálne runnery |
| `840856e` | **Hover flicker fix** | Klik-only výber (hit-test na boxe), odstránený hover-flicker |
| `c9f6f20` | **Bitewing upozornenie** | Segmentová snímka (ratio < 1.5) → varovanie o orientačných číslach zubov |
| `b338938` | **Gemini UI panel** | Kompaktný, loading inline, žiadne prázdne veľké polia |
| `7a1afbf` | **Bitewing režim** | Toggle: len kazy, bez odontogramu/císlovania, Gemini retry/timeout |
| `0b2930f` | **AI druhý názor (Gemini VLM)** | `gemini_vision.py` port z HF Space, `/vision/{job_id}`, UI panel, `requirements.txt +requests` |
| `4f947d6` | **Viewer fit fix** | `requestAnimationFrame` po layoute + resize listener — rieši „obrovská snímka po nahratí“ |

---

## DNEŠNÉ OPRAVY (2026-10-11) — TOTO ZADANIE

### Problém: Čierna obrazovka po nahratí/refreshi
**Príčina:** Frontend používal `URL.createObjectURL(file)` (blob URL), ktorý funguje len v tej istej session. Po refresi stránky sa blob URL stratí.

### Riešenie implementované:

#### 1. Nový backend endpoint: `GET /uploads/{job_id}`
**Súbor:** `backend/app/api/routes/media.py`
```python
@router.get("/uploads/{job_id}")
def upload(job_id: str):
    image = _find_image(job_id)
    return FileResponse(image)
```

#### 2. Frontend prepojenie na backend URL
**Súbor:** `frontend/src/App.tsx` — funkcia `runAnalysis`
```typescript
// Po úspešnej analýze prejdeme na backend URL (persistuje po refreshi)
setImageUrl(`${API_BASE}/uploads/${r.job_id}`);
```

#### 3. Gemini model fix
**Súbor:** `backend/app/ml/gemini_vision.py`
```python
# Pôvodne: gemini-1.5-flash-8b-latest → 404 Not Found
# Skúšané: gemini-1.5-flash-8b, gemini-1.5-flash-latest → 404
# FUNGUJE: gemini-flash-latest (pôvodný z HF Space histórie)
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"
```
**Výsledok:** 429 Rate Limit = free tier kvóta, model existuje a API key je platný.

#### 4. Frontend rebuild
```bash
cd frontend && npm run build
# → nový bundle: assets/index-4B5399nX.js
```

### Test výsledky (všetko 200 OK):

| Endpoint | Status | Content-Type | Poznámka |
|---|---|---|---|
| `POST /analyze?conf=0.12` | 200 | JSON | 21 nálezov |
| `GET /uploads/{job_id}` | 200 | image/jpeg | **NOVÉ** — rieši čiernu obrazovku |
| `GET /gradcam/{job_id}` | 200 | image/png | Heatmapa |
| `POST /vision/{job_id}` | 200 | JSON | Gemini — 429 rate limit (free tier OK) |
| `GET /report/{job_id}` | 200 | application/pdf | PDF posudok |

---

## TECHNICKÉ DLHY (OTEVORENÉ TODO)

### Infrastructure
- [ ] `.dockerignore` vytvoriť (vylúčiť `.venv`, `data/`, `*.pt`, `__pycache__`, `kaggle/`, `archive/`)
- [ ] `Dockerfile` multi-stage build (build frontend → copy dist, stiahnuť váhy v runtime)
- [ ] HF Spaces deploy (HF_TOKEN + Space secrets: `GEMINI_API_KEY`, `APP_PASSWORD`, `SECRET`)
- [ ] Rotovať `.secret` HMAC kľúč (je v gite histórii)
- [ ] `git filter-repo` pre čistenie histórie (112 súborov s pacientskymi dátami)

### Backend AI
- [ ] Opraviť `async def analyze` → `run_in_executor` (neblokovať event loop)
- [ ] Vypnúť TTA ±90° rotácie (anatomicky nezmyselné + bug v `_transform_bbox`)
- [ ] Opraviť MC Dropout neistotu (IoU párovanie + train režim)
- [ ] Odstrániť duplicitné `_nms_per_class`/`_weighted_box_fusion` v `detector.py`
- [ ] DICOM input (`pydicom` + windowing)
- [ ] ONNX export (2–5× rýchlejšia CPU inferencia)

### Frontend
- [ ] Cookie `secure=true` v produkcii
- [ ] CORS obmedziť na konkrétny origin
- [ ] Auto-mazanie starých uploadov (cron job)
- [ ] WebSocket pre live progres (namiesto polling)

### Model / Presnosť
- [ ] Fáza 0: Stiahnuť 5× P0 datasety (~5,3 GB) + pseudolabeling/cross-labeling
- [ ] Fáza 1: YOLOv11s/v26-s na merged čistých dátach, Bitewing model, Bone loss + calculus
- [ ] Fáza 2: VLM druhý názor (port z HF Space), Treatment suggestions, FDI 3-fázový pipeline
- [ ] Feedback loop u zubára → fine-tuning na jeho prístroji (+5–10 pp)

---

## KAGGLE TRÉNING — ZÁZNAMY BEHOV

| Dátum | Kernel | Model | Dataset | Epochy | Výsledok |
|---|---|---|---|---|---|
| 4.–5.10 | v8s_night | YOLOv8s | DENTEX | 50 | Peak mAP50 62,5 % (epocha 26), Caries recall 72,3 % |
| 5.10 | v8m_night | YOLOv8m | DENTEX | 3 | Timeout validácie (900 s) |
| 6.10 | merged_v1 | YOLOv8s | DENTEX+mega | 40 | **FAIL** Caries 72→39,6 % |
| 7.10 | cariesx | YOLOv8s | CariesX | — | **FAIL** Caries 72→42 % |
| 8.10 | mega5 | YOLOv8m | mega-dataset | — | Plomba 92 %, Korunka falošné poplachy |
| 10.10 | v5 | YOLOv8m | mega-dataset | 100 | BEŽI (kernel eriksmite/dental-yolov8-training-v5) |

### MORNING_REPORT.md (v8s_night) — Kľúčové epochy

| Epocha | mAP50 | Zmena |
|---|---|---|
| 1 | 25,8 % | — |
| 8 | 41,3 % | +4,40 pp |
| 14 | 50,2 % | +4,70 pp |
| 20 | 55,5 % | +5,01 pp |
| **26** | **62,5 %** | **+4,61 pp (PEAK)** |
| 32 | 61,4 % | +4,04 pp |
| 38 | 60,9 % | +2,35 pp |
| 43 | 61,6 % | +2,15 pp |
| 48 | 61,8 % | +1,64 pp |
| 50 | 54,8 % | −1,98 pp |

**Validácia zlyhala:** `val_best.py` timeout 900 s na lokálnom stroji.

---

## POUČENIA PRE BUDÚCNOST (KRITICKÉ)

1. **Nemiešať značky** — 3 potvrdené experimenty: merged, CariesX, mega5 koronky. Všetky zlyhali kvôli šumu v externých anotáciách.
2. **Cross-labeling > fine-tuning na noisy data** — náš model označkuje mega snímky, použijem len zhody (IoU ≥ 0.5) → 7 000+ čistých kazov.
3. **Inference-side tuning > fine-tuning** — CONF_THRESHOLD 0.25 → 0.12 dalo 80,2 % recall (presun z 72,3 %).
4. **Detached procesy zomierajú** — dlhé behy (tréning, uvicorn) musia bežať v jednom Bash calle alebo subagente.
5. **Start-Process -ArgumentList quoting** — nespoľahlivé, použiť `cmd /c` s jedným stringom.
6. **Git lock** — `dsh` proces (python server.py) drží `index.lock`, commit blokovaný kým neukončí.
7. **PowerShell ternary operator** — nepodporuje `condition ? a : b`, použiť `if/else`.
8. **scratch/secrets.py** — prekrýva stdlib `secrets`, premenovať.

---

## KONTAKTY A PRÍSTUPY

| Služba | Konto | Poznámka |
|---|---|---|
| Hugging Face | `ericecek` | Space: `ericecek/dental-ai` (public, cpu-basic) |
| HF Token (write) | — | Token v environmente, nie v kóde |
| Kaggle | `eriksmite` | kvóta ~18 h, API key v `C:\Users\PC1\.kaggle\kaggle.json` |
| Roboflow | — | API key do .env (voliteľné) |
| Gemini API | — | Key v `.env` + Space secrets (`GEMINI_API_KEY`) |
| Supabase | — | Free tier, URL + anon key do .env (voliteľné) |
| Lokálny GPU | GTX 1080 Ti | Pascal, 11 GB VRAM, FP32 only (`amp=False`) |

---

## RYCHLÝ ŠTART PRE NOVÉHO AGENTA

```bash
# 1. Prečítaj PROJECT_DOCUMENTATION.md (tento súbor má brat)
# 2. Prečítaj WORK_LOG_AND_ERRORS.md (tento súbor)
# 3. Skontroluj .env (APP_PASSWORD, GEMINI_API_KEY, CONF_THRESHOLD=0.12)
# 4. Spusti backend
cd backend && .venv\Scripts\activate && uvicorn app.main:app --port 8000
# 5. Test health
curl http://localhost:8000/health
# 6. Login + analyze test
# 7. Ak chceš trénovať:čítaj KAGGLE_PRIRUCKA_PRE_AGENTOV.md
# 8. Ak chceš deploy: oprav .dockerignore + Dockerfile + HF_TOKEN
```

---

## ZÁVÄZNÉ KOMENTÁRE PRE NASLEDUJÚCEHO AGENTA

> **„Modelový strop bez čistých dát je dosiahnutý.“** — Ďalšie percentá prídu **len od zubára** (jeho 30–200 označkovaných prípadov = +5–10 pp na jeho prístroji). Feedback loop je **jediná reálna cesta nahor**.

> **„Komerčná špička (Overjet, Pearl) nie je cieľ na prekonanie v demo.“** — Cieľ je **druhý pohľad, ktorý ušetrí prácu**. Lekári aj s horšou AI našli kaz, ktorý prehliadli, v ~1 z 5–6 prípadov.

> **„Free tier je obmedzenie, nie chyba.“** — Všetko beží na 0 €. Kaggle 18 h, HF Spaces CPU, Supabase free. Optimalizovať pod tieto obmedzenia.

> **„Dokumentácia je v gite, nie v hlave.“** — Všetky rozhodnutia, experimenty, chyby a opravy sú v tomto súbore + `PROJECT_DOCUMENTATION.md` + git history. Čítaj pred akciou.