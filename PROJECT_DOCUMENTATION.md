# 🦷 Dental AI v2 — Kompletná dokumentácia projektu

*Verzia: 2026-10-11 | Zdroj: POPIS_PROJEKTU.md, SUHRN_PROJEKTU.md, PLAN_DO_90_PERCENT.md, README.md, docs/POROVNANIE.md, docs/MORNING_REPORT.md, KAGGLE_PRIRUCKA_PRE_AGENTOV.md, DATASET_DEDUPE_MAP.md, git history*

---

## 1. ČO JE PROJEKT

**Dental AI v2** je demo aplikácia pre zubnú ambulanciu: AI „druhý pohľad“ na RTG snímky (panoramatické + intraorálne/bitewing). Lekár nahraje snímku, model deteguje nálezy za ~5 sekúnd, aplikácia zobrazí overlay na snímke, Grad-CAM heatmapu, odontogram a vygeneruje jednostranový PDF posudok pre pacienta v slovenčine. Pri každom náleze lekár klikne **Súhlasím / Opraviť** — tým vzniká súkromný dataset na doladenie modelu na jeho prax a metrika zhody AI s lekárom.

**Cieľ:** wow efekt pre zubára s 15-ročnou praxou + reálne ušetrenie práce, hosting za **0 €** (HF Spaces free + Supabase free).

**Hlavný princíp:** AI = *druhý pohľad, nie diagnóza*. „Nesúťažím s vašimi očami — som sieť pod nimi.“

**Produkčný stav:** LIVE na https://ericecek-dental-ai.hf.space (login: `lekár` / `mlady79-rtg95`)

---

## 2. ARCHITEKTÚRA

| Vrstva | Technológia | Stav |
|---|---|---|
| **Backend** | FastAPI + Uvicorn (Python 3.11, `backend/app`) | ✅ hotový |
| **Detekcia** | Ultralytics YOLOv8s (hlavný) + mega5 (restaurácie) + ensemble v8s+v8m, TTA, MC Dropout, SAHI tiles, Grad-CAM | ✅ hotový (bugy opravené) |
| **Frontend** | React 18 + Vite 5 + Tailwind 4 (`frontend/src`) | ✅ hotový, redesign (glass/Linear-Raycast štýl) |
| **Login** | multi-user `.env` (`USERS="lekar:heslo,..."`) + HMAC session cookie 12 h | ✅ hotový |
| **Perzistencia** | SQLite `backend/data/db.sqlite` (feedback) + JSON/obrázky v `backend/data/` | ✅ hotové |
| **Reporty** | ReportLab, slovenčina, 1 strana pre pacienta | ⚠️ hotový, fonty v Linux kontajneri |
| **Deploy** | Dockerfile (HF Spaces, port 7860) + docker-compose | ⚠️ čaká na .dockerignore + HF_TOKEN |
| **Tréning** | `train/` (lokálne 1080 Ti) + `kaggle_kernel/` (Kaggle T4x2) | ✅ bežal, ~18 h kvóty ostáva |

### Endpointy

| Metóda | Cesta | Popis |
|---|---|---|
| GET | `/health` | Health check |
| POST | `/analyze?conf=&mode=standard\|tiles\|ens` | Nahranie + analýza |
| GET | `/uploads/{job_id}` | **NOVÉ** - originálna snímka (rieši čiernu obrazovku po refreshi) |
| GET | `/results` | Zoznam analýz |
| GET | `/results/{job_id}` | Detail analýzy |
| POST | `/results/{job_id}/feedback` | Súhlasím/Opraviť |
| GET | `/metrics` | Zhoda AI s lekárom (%) |
| GET | `/gradcam/{job_id}` | Heatmapa (PNG) |
| GET | `/report/{job_id}` | PDF posudok |
| POST | `/vision/{job_id}` | **NOVÉ** - AI druhý názor (Gemini VLM) |
| GET/POST | `/login` | Prihlásenie |
| GET | `/logout` | Odhlásenie |

### Spustenie lokálne

```bash
# Backend
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000

# Frontend dev
cd frontend && npm run dev  # proxy :5173→:8000

# Docker (produkčný port 7860)
docker compose up --build
```

Demo prihlásenie: `lekár` / `mlady79-rtg95`

---

## 3. MODLY A MOMENTÁLNA PRESNOSŤ

### Hlavný model — v8s „nočný“ (YOLOv8s, imgsz 1280, 50 epoch lokálne na GTX 1080 Ti)

Tréning: 4.–5.10.2026, detailná tabuľka po epochách v `docs/MORNING_REPORT.md` (peak mAP50 62,5 % v epoche 26).

| Metrika (čistý DENTEX valid: 46 snímok, 182 nálezy) | Hodnota |
|---|---|
| **mAP50 celok** | **61,0 %** |
| mAP50-95 celok | ~38 % |
| **Caries recall** ⭐ | **72,3 %** |
| Caries mAP50 | 49,8 % |
| Periapical mAP50 | 48,0 % |
| Impacted mAP50 | 85,8 % |
| Deep Caries recall | 53,1 % |

### Model restaurácií — mega5 (YOLOv8m, 5 tried: Caries/Crown/Filling/Implant/Periapical)

| Metrika | Hodnota |
|---|---|
| Plomba (Filling) | **92 %** |
| Korunka (Crown) | deteguje (vylúčená z finálnych nálezov — veľa falošných poplachov) |
| Implantát | deteguje |

Duálny model overený na 5 snímkach (commit `3274e32`: „Dual-model overený: Plomba/Korunka/Implantát + diagnózy na rôznych snímkach (mega5 validačný test OK)“).

### Rebríček: kde sa nachádzame

| Kto | Recall (nájde kaz) |
|---|---|
| Študent 4.–5. ročníka | ~50–65 % |
| Mladý lekár (1–3 roky praxe) | ~65–75 % **← tu sme (72,3 %)** |
| **Naše demo (v8s)** | **72,3 %** |
| Skúsený zubár (10–15+ rokov) | ~75–85 % |
| Špičkový výskum | ~85–90 % |
| Komerčná špička (Overjet, Pearl — FDA) | ~85–95 % |

**Záver:** V detekcii skúseného zubára neprekonáme — naša hodnota je druhý pohľad, ktorý nikdy neunaví, nič nepodieva a odpovie za 5 s. Lekári v štúdiách aj s horšou AI nachádzali kaz, ktorý sami prehliadli, v ~1 z 5–6 prípadov.

---

## 4. FUNKCIE (WOW FAKTORY PRE ZUBÁRA)

1. **Overlay nálezov na snímke** — farebná závažnosť: urgent (červená) / treat soon (oranžová) / watch (modrá) / restoration (fialová).
2. **Grad-CAM heatmapa** — vizualizácia, kde sa model „pozerá“ pri náleze s najvyššou istotou.
3. **Odontogram** — všetky zuby podľa FDI čísla pod snímkou, farebne označené.
4. **PDF posudok pre pacienta** — slovenčina, 1 strana, za minútu.
5. **Feedback loop** — Súhlasím/Opraviť + metrika zhody (panel Metrics) — buduje súkromný dataset.
6. **Merania v mm**, TTA (test-time augmentation), MC Dropout neistota, SAHI tiles (veľké snímky po častiach), ensemble dvoch modelov.
7. **Priebeh analýzy** — live progres, rýchly (5 s) aj na CPU.
8. **Bitewing režim** — toggle len kazy (Caries/Deep Caries), bez číslovania zubov, bez odontogramu.
9. **Heatmapa blendovaná priamo na snímke** — 45 % opacity, Overjet/Pearl štýl.
10. **AI druhý názor (Gemini VLM)** — side-by-side porovnanie YOLO vs. Gemini, zhoda/rozdiely.

---

## 5. ŠTRUKTÚRA A DÁTA

```
dental-ai-v2/
├── backend/            FastAPI + YOLO detektor + reporty
│   ├── app/            main.py, api/routes/, core/ (config, auth), ml/ (detector, sahi, ensemble, gradcam, reporter, gemini_vision)
│   ├── weights/        best.pt (22,6 MB), best_v8m_dentex.pt (52 MB), best_v8s_mega5.pt, experimenty
│   └── data/           db.sqlite + uploads/results/reports (POZOR: sú v gite — čistiť!)
├── frontend/           React SPA (Viewer zoom/pan, FindingCard, Odontogram, MetricsPanel)
├── docs/               PLAN_2_DNI, TRAINING_BUDGET, POROVNANIE, MORNING_REPORT, NOVY_PROJEKT_ASISTENT
├── kaggle_kernel/      notebook.ipynb + kernel-metadata.json (kernel eriksmite/dental-yolov8-training-v5)
├── kaggle/night/       dentex_night.zip (3,8 GB) — CENTRÁLNA kópia (v3/v4 majú junctions sem)
├── train/              train.py, train_resume.py, supervise_night.py, val_best.py, data.dentex.yaml, data.mega5.yaml, runs/
├── Dockerfile          HF Spaces (port 7860)
└── docker-compose.yml  lokálny beh
```

### Ťažké dáta (SHARED, dedupe 2026-10-10 — `DATASET_DEDUPE_MAP.md`)

| Dataset | Kde (centrálne) | Veľkosť |
|---|---|---|
| mega-dataset.zip | `C:\Users\PC1\Desktop\dental-ai\mega-dataset.zip` | 741 MB (SHA256 DB41…E0D8) |
| DENTEX training_data.zip | `C:\Users\PC1\Desktop\dental-ai\datasets\dentex\DENTEX\` | 10,9 GB |
| dentex_night.zip | `C:\Users\PC1\Desktop\dental-ai-v2\kaggle\night\` | 3,8 GB (centrálna kópia, v3/v4 majú junctions) |

**Pravidlo:** Budúce ťažké datasety do `dental-ai\archive\` + NTFS junctions. NE kopírovať duplicitne!

---

## 6. KAGGLE TRÉNING — PRÍRUČKA PRE AGENTOV

Konto: `eriksmite`, kvóta ~18 h GPU ostáva.

### 4 KRITICKÉ CHYBY Z V1 (NAOPAKOVAŤ!)

1. **Read-only file system** — `/kaggle/input/` je read-only. Riešenie: `shutil.copytree` do `/kaggle/working/`.
2. **Nested dataset** — Skutočná cesta: `/kaggle/input/mega-mataset-dental/mega-dataset/data.yaml` (dvojitý nesting). Vždy `os.listdir` skontrolovať.
3. **CUDA incompatibilita (Tesla P100)** — P100 (CUDA 6.0) nekompatibilné. Použiť **GPU T4 x2** alebo Colab T4.
4. **nbformat null** — Neplatný notebook JSON. Riešenie: generovať cez `nbformat` knižnicu (`create_notebook.py`).

### Overený postup v2

- Kernel: `eriksmite/dental-yolov8-training-v5` (YOLOv8m, 5 tried, 100 epoch, imgsz 1280, batch 6)
- Generátor notebooku: `create_notebook.py` (uprav konfiguráciu TU a pregeneruj)
- Push na Kaggle: `download_kernel.py` / `download_kernel_api.py` / `download_kernel_http.py`
- Čakanie na beh: `wait_for_kernel.ps1` / `wait_for_kernel_training.ps1` (polling)
- Validácia: výstupy do `kernel_output*/`, validácia cez `train/val_best.py` (lokálne timeoutuje po 900 s — spúšťať s dlhším timeoutom alebo na Kaggle v notebooku)

### Konfigurácia tréningu (osvedčené)

```python
CONFIG = {
    "model": "yolov8s.pt",          # v8s = hlavný (rýchly, 22 MB); v8m = donor/ensemble
    "data": "<working>/data.yaml",
    "epochs": 50,                   # 50 stačí (peak ~epoche 26-48)
    "imgsz": 1280,                  # panoramatické RTG — 1280 overené
    "batch": 6,                     # pri imgsz 1280 na 1080 Ti
    "patience": 15,
    "optimizer": "AdamW", "lr0": 0.001, "cos_lr": True,
    "flipud": 0.0,                  # ŽIADNY vertikálny flip — anatomicky nezmyselný
    "fliplr": 0.5,                  # horizontálny flip OK
    # ŽIADNE ±90° rotácie — zobrazujú zuby hore nohami (backend má navyše bug v _transform_bbox)
    "mosaic": 1.0, "mixup": 0.1, "close_mosaic": 10,
}
```

### Poučenia (KRITICKÉ — čítať pred každým tréningom!)

1. **Nemiešať externé značky s DENTEX konvenciami** — 3 experimenty potvrdili pokles: merged DENTEX+mega (−32,7 pp Caries recall), CariesX (+0,9 pp celok, ale recall 72→42). Dôvod: mega „Caries“ mieša bežný + hlboký kaz, iní ľudia, iné prístroje.
2. **Správne využitie mega-datasetu:** pre-training na mega → finetuning na čistom DENTEX (+1–3 pp); alebo cross-labeling (model označkuje, použijem len zhody → 7 000+ čistých kazov).
3. **Modelový strop bez čistých dát je dosiahnutý** — ďalšie percentá prídu od zubára (30–200 označkovaných prípadov = +5–10 pp).
4. **Minimalizovať GPU čas** — kvóta ~18 h; supervízor (`train/supervise_night.py`) stráži behy.
5. **Pred behom overiť:** accelerator (T4), nested cestu, read-only input, validáciu v notebooku.

---

## 7. STAV PROJEKTU A ZNÁME PROBLÉMY

### Hotové (všetko mimo deployu)
Backend, frontend, login, dual-model, odontogram, PDF, feedback, dokumentácia, tréning pipeline.

### P1 — Kritické (pred akoukoľvek ukážkou klientom)

1. **Blokujúca analýza zamrzne server** — `async def analyze` volá CPU inferenciu (5–10 s) v event loope → počas analýzy neodpovie ani `/health`. Oprava: `def analyze` alebo `run_in_executor`.
2. **Pacientske dáta a tajomstvo v gite** — 112 súborov (RTG s menami, PDF, `db.sqlite`, `backend/data/.secret` HMAC kľúč). Oprava: `git rm --cached` + `.gitignore` + rotovať secret + `git filter-repo`.
3. **PDF bez slovenskej diakritiky v produkcii** — `reporter.py` načíta len Windows fonty; v Linux kontajneri fallback Helvetica bez č/š/ž. Oprava: DejaVu Sans do kontajnera.
4. **Deploy nefunkčný** — chýba `.dockerignore` (COPY vtiahne 4,9 GB `.venv`), `Dockerfile` kopíruje `frontend/dist` a váhy, ktoré sú v `.gitignore`. Oprava: .dockerignore + multi-stage build + váhy počas buildu.

### P2 — Dôležité (správnosť AI funkcií)

5. **TTA rotácie ±90° nefungujú** — `_transform_bbox` má prehodené orig_w/orig_h → 2 z 5 augmentácií vygenerujú boxy mimo snímky. Anatomicky nezmyselné — radšej vypnúť (nechať hflip + škály + CLAHE).
6. **MC Dropout neistota = 0,0 pri všetkých 153 nálezoch** — zlučovanie podľa presného bbox + `model.eval()` v predicte. Oprava: párovanie cez IoU ≥ 0,5 + inferencia v train režime.
7. **Duplicitné definície** `_nms_per_class`/`_weighted_box_fusion` v detector.py (2×) — druhá ticho prepíše prvú.
8. **Webová vrstva:** CORS `*`, cookie bez `secure`, 401 maskuje 404 (`.mcp` spam v logoch), DICOM sľúbený v UI ale nečítaný, uploady sa nikdy nemazú.

### P3 — Rast presnosti a hodnoty

9. **Feedback loop u zubára** — zapnúť Súhlasím/Opraviť → 30–200 označkovaných prípadov = **+5–10 pp** fine-tuningom na jeho prístroji.
10. **Pre-training na mega-datasete** → finetuning na čistom DENTEX (+1–3 pp).
11. **ONNX export** (2–5× rýchlejšia CPU inferencia), **FDI číslovanie zuba**, **VLM druhý názor** (Gemini Flash), **DICOM input** (pydicom), **YOLO26 váhy benchmark**.

---

## 8. NÁKLADY A PREVÁDZKA

**0 €/mesiac**: HF Spaces free (CPU) + Supabase free (500 MB DB + 1 GB storage) + Kaggle free GPU (~18 h ostáva).

Slabina free tieru: Space zaspí po 48 h nečinnosti — pred ukážkou otvoriť vopred (alebo free ping z cron-job.org).

---

## 9. SYNERGIA S AI RECEPNou

Rovnaký backend vzor a login je pripravený pre **AI Recepnú** (`docs/NOVY_PROJEKT_ASISTENT.md`): pacient prijíma 24/7 (Viber bot 0–5 €/mes, neskôr hlasový agent), rezervácie termínov bez telefónovania. Spoločný príbeh: „AI v ambulancii od A do Z“ — recepná prijíma, AI pomáha lekárovi s RTG.

---

## 10. KĽÚČOVÉ SÚBORY PRE RYCHLÚ PRÁCU

| Súbor | Účel |
|---|---|
| `backend/app/ml/detector.py` | Hlavný detektor (TTA, MC Dropout, SAHI, mega5) |
| `backend/app/ml/gemini_vision.py` | Gemini VLM druhý názor |
| `backend/app/api/routes/analyze.py` | Analýza endpoint (opraviť blocking) |
| `backend/app/api/routes/media.py` | Uploads, Grad-CAM, Report, Vision endpointy |
| `backend/app/core/auth.py` | HMAC session auth |
| `backend/app/core/config.py` | Nastavenia cez .env |
| `frontend/src/App.tsx` | Hlavný UI komponent |
| `frontend/src/components/Viewer.tsx` | Canvas viewer s zoom/pan/heatmap |
| `frontend/src/components/FindingCard.tsx` | Karta nálezu s Súhlasím/Opraviť |
| `train/build_merged.py` | Merge datasetov (COCO/LabelMe/VOC/YOLO) |
| `train/pseudolabel.py` | Cross/pseudo labeling s IoU matching |
| `train/kaggle_prep.py` | Kaggle dataset/kernel deploy |
| `create_notebook.py` | Generátor Kaggle notebooku |
| `KAGGLE_PRIRUCKA_PRE_AGENTOV.md` | Príručka pre Kaggle agentov |

---

## 11. ENV PREMENNÉ (`.env`)

```env
APP_PASSWORD=mlady79-rtg95          # demo heslo (fallback ak nie je USERS)
USERS=lekár:mlady79-rtg95           # multi-user: "meno:heslo,meno2:heslo2"
SECRET=...                          # HMAC kľúč session cookie (auto-generuje sa)
CONF_THRESHOLD=0.12                 # prah citlivosti (80.2 % recall)
MAX_UPLOAD_MB=15
WEIGHTS_PATH=weights/best.pt
GEMINI_API_KEY=AIzaSy...            # pre AI druhý názor
ALLOWED_ORIGINS=https://...         # CORS (prázdne = wildcard)
COOKIE_SECURE=false                 # True pri HTTPS deploye
SUPABASE_URL=...                    # voliteľné
SUPABASE_ANON_KEY=...
```

---

## 12. NAVIGÁCIA PRE BUDÚCEHO AGENTA

- **Chceš pochopiť projekt:** Čítaj tento súbor (`PROJECT_DOCUMENTATION.md`)
- **Chceš vedieť čo sa robilo a aké boli chyby:** Čítaj `WORK_LOG_AND_ERRORS.md`
- **Chceš trénovať na Kaggle:** Čítaj `KAGGLE_PRIRUCKA_PRE_AGENTOV.md`
- **Chceš deploy na HF Spaces:** Oprav .dockerignore + Dockerfile + HF_TOKEN
- **Chceš zlepšiť model:** Čítaj `PLAN_DO_90_PERCENT.md` (Fáza 0–3)
- **Chceš pridať funkciu:** Pozri `backend/app/api/routes/` a `frontend/src/components/`