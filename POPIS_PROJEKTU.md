# 🦷 Dental AI v2 — podrobný popis projektu

*Vytvorené PI-Desktop 2026-10-10 (dokument dorobený namiesto ZCode session `sess_d3a979f8`). Zdroje: README, docs/POROVNANIE.md, docs/MORNING_REPORT.md, ZCode session, analýza 3 agentov (OpenCode, Hermes, dsh/Kilo).*

## 1. Čo projekt je

**Dental AI v2** je demo aplikácia pre zubnú ambulanciu: AI „druhý pohľad" na RTG snímky (panoramatické + intraorálne). Lekár nahraje snímku, model deteguje nálezy za ~5 sekúnd, aplikácia zobrazí overlay na snímke, Grad-CAM heatmapu, odontogram a vygeneruje jednostranový PDF posudok pre pacienta v slovenčine. Pri každom náleze lekár klikne **Súhlasím / Opraviť** — tým vzniká súkromný dataset na doladenie modelu na jeho prax a metrika zhody AI s lekárom.

**Cieľ:** wow efekt pre zubára s 15-ročnou praxou + reálne ušetrenie práce, hosting za **0 €** (HF Spaces free + Supabase free).

**Hlavný princíp:** AI = *druhý pohľad, nie diagnóza*. „Nesúťažím s vašimi očami — som sieť pod nimi."

## 2. Architektúra

| Vrstva | Technológia | Stav |
|---|---|---|
| Backend | FastAPI + Uvicorn (Python 3.11, `backend/app`) | ✅ hotový |
| Detekcia | Ultralytics YOLOv8s (hlavný) + mega5 (restaurácie) + ensemble v8s+v8m, TTA, MC Dropout, SAHI tiles, Grad-CAM | ✅ hotový (bugy nižšie) |
| Frontend | React 18 + Vite 5 + Tailwind 4 (`frontend/src`) | ✅ hotový, redesign (glass/Linear-Raycast štýl) |
| Login | multi-user `.env` (`USERS="lekar:heslo,..."`) + HMAC session cookie 12 h | ✅ hotový |
| Perzistencia | SQLite `backend/data/db.sqlite` (feedback) + JSON/obrázky v `backend/data/` | ✅ hotové |
| Reporty | ReportLab, slovenčina, 1 strana pre pacienta | ⚠️ hotový, ale fonty (nižšie) |
| Deploy | Dockerfile (HF Spaces, port 7860) + docker-compose | ⚠️ čaká na HF_TOKEN |
| Tréning | `train/` (lokálne 1080 Ti) + `kaggle_kernel/` (Kaggle) | ✅ bežal, ~18 h kvóty ostáva |

**Endpointy:** `GET /health`, `POST /analyze?conf=&mode=standard|tiles|ens`, `GET /results`, `GET /results/{id}`, `POST /results/{id}/feedback`, `GET /metrics`, `GET /report/{id}` (PDF), `GET /gradcam/{id}`, `GET|POST /login`, `GET /logout`.

**Spustenie lokálne:** `cd backend` → venv → `pip install -r requirements.txt` → `uvicorn app.main:app --port 8000`; frontend dev: `cd frontend && npm run dev` (proxy :5173→:8000). Docker: `docker compose up --build` (port 7860). Prihlásenie demo: `lekár` / `zmen-ma`.

## 3. Modely a momentálna presnosť

### Hlavný model — v8s „nočný" (YOLOv8s, imgsz 1280, 50 epoch lokálne na GTX 1080 Ti)

Tréning: 4.10.–5.10.2026, detailná tabuľka po epochách v `docs/MORNING_REPORT.md` (peak mAP50 62,5 % v epoche 26).

| Metrika (čistý DENTEX valid: 46 snímok, 182 nálezov) | Hodnota |
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
| Korunka (Crown) | deteguje (vylúčená z finálnych nálezov — veľa falošných poplachov, commit `7710a03`) |
| Implantát | deteguje |

Duálny model overený na 5 snímkach (ZCode todo: „Mega5 integrácia — HOTOVÉ").

### Rebríček: kde sa nachádzame (orientačné, z literatúry — ZCode session 6.10.)

| Kto | Recall (nájde kaz) |
|---|---|
| Študent 4.–5. ročníka | ~50–65 % |
| Mladý lekár (1–3 roky praxe) | ~65–75 % **← tu sme (72,3 %)** |
| **Naše demo (v8s)** | **72,3 %** |
| Skúsený zubár (10–15+ rokov) | ~75–85 % |
| Špičkový výskum | ~85–90 % |
| Komerčná špička (Overjet, Pearl — FDA) | ~85–95 % |

**Záver:** v detekcii skúseného zubára neprekonáme (a nemusíme) — naša hodnota je druhý pohľad, ktorý nikdy neunaví, nič nepodieva a odpovie za 5 s. Lekári v štúdiách aj s horšou AI nachádzali kaz, ktorý sami prehliadli, v ~1 z 5–6 prípadov.

### Skúsenosti z experimentov (zdokumentované v gite)

- **Merged DENTEX + 2 500 kazov z mega-datasetu**: FAIL — Caries recall 72,3→39,6 % (−32,7 pp). Príčina: mega-dataset má v anotáciách šum (mieša bežný a hlboký kaz, iní ľudia na iných prístrojoch). Archivované ako poučenie (`1ef62af`).
- **CariesX experiment**: celok +0,9 pp, ale Caries recall 72→42 % — tretie potvrdenie konfliktu externých značiek s DENTEX konvenciami.
- **Správny postup na mega-dataset**: (a) pre-training na mega → finetuning na čistom DENTEX (+1–3 pp), alebo (b) cross-labeling — náš model označkuje mega snímky, použijem len zhodné (dá 7 000+ čistých kazov).

## 4. Funkcie (wow faktory pre zubára)

1. **Overlay nálezov na snímke** — farebná závažnosť: urgent / treat soon / watch.
2. **Grad-CAM heatmapa** — vizualizácia, kde sa model „pozerá".
3. **Odontogram** — všetky zuby podľa FDI čísla pod snímkou, farebne označené.
4. **PDF posudok pre pacienta** — slovenčina, 1 strana, za minútu.
5. **Feedback loop** — Súhlasím/Opraviť + metrika zhody (panel Metrics) — buduje súkromný dataset.
6. **Merania v mm**, TTA (test-time augmentation), MC Dropout neistota, SAHI tiles (veľké snímky po častiach), ensemble dvoch modelov.
7. **Priebeh analýzy** — live progres, rýchly (5 s) aj na CPU.

## 5. Štruktúra a dáta

```
dental-ai-v2/
├── backend/            FastAPI + YOLO detektor + reporty
│   ├── app/            main.py, api/routes/, core/ (config, auth), ml/ (detector, sahi, ensemble, gradcam, reporter)
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

Ťažké dáta (SHARED, dedupe 2026-10-10 — `DATASET_DEDUPE_MAP.md`): mega-dataset.zip (741 MB, SHA256 DB41…E0D8) v `C:\Users\PC1\Desktop\dental-ai\`; DENTEX training_data.zip (10,9 GB) v `dental-ai\datasets\dentex\DENTEX\`; dentex_night.zip (3,8 GB) centrálne v `dental-ai-v2\kaggle\night\` s junctionmi z v3/v4. **Budúce ťažké datasety do `dental-ai\archive\` + junctions.**

## 6. Stav projektu a známe problémy

**Hotové:** všetko mimo deployu (ZCode 6.10.: „všetko mimo Kaggle tréningu je dokončené") — backend, frontend, login, dual-model, odontogram, PDF, feedback, dokumentácia, tréning pipeline.

**Chýba / čo vylepšiť (prioritne — detaily v `SUHRN_PROJEKTU.md`):**
1. HF Spaces deploy (čaká na HF_TOKEN).
2. Kritické bugy z analýzy 3 agentov (10.10.): blokujúca `async def analyze` (mrzne celý server), TTA ±90° rotácie (prehodené orig_w/orig_h → 2 z 5 augmentácií nepoužiteľné), MC Dropout neistota = 0.0, PDF fonty bez slov. diakritiky v Linux kontajneri, duplicitné definície v detector.py.
3. Bezpečnosť: pacientske dáta + `backend/data/.secret` v gite (112 súborov) → `git rm --cached` + rotovať secret; chýba .dockerignore (COPY vtiahne 4,9 GB .venv).
4. Kaggle príručka pre agentov → `KAGGLE_PRIRUCKA_PRE_AGENTOV.md`.
