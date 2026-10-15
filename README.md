# 🦷 Dental AI V2

**Automatická detekcia zubných patológií z rentgenových snímok pomocou YOLOv8**

Nový, čistý projekt (žiadna závislosť na starom `dental-ai`). Cieľ: **verejne dostupné demo na free hostingu s databázou**, ktoré urobí wow efekt na zubára s 15-ročnou praxou a reálne mu ušetrí prácu.

## Prehľad projektu

Dental AI V2 je systém na analýzu dentálnych rentgenových snímok (panoramatické, periapikálne, bitewing) s využitím hlbokého učenia. Systém detekuje 19 tried zubných patológií a vytvára automatizované správy s odporúčaniami.

## Architektura

| Vrstva | Technológia | Hosting |
|---|---|---|
| Frontend | React + Vite + Tailwind | HF Spaces (statický build v kontajneri) |
| Backend | FastAPI + Uvicorn | HuggingFace Spaces — Docker, free CPU |
| Model | YOLOv8 (hotové váhy → neskôr retrén) | CPU inferencia ~1–2 s/snímka |
| Databáza | Supabase Postgres (free 500 MB) | supabase.com |
| Súbory (RTG, PDF) | Supabase Storage (free 1 GB) | supabase.com |
| Reporty | ReportLab (slovenčina, 1 strana pre pacienta) | — |
| CI | GitHub Actions → auto-deploy do Space-u | github.com |

**Náklady: 0 €.** Jediná slabina free tieru: Space zaspí po 48 h nečinnosti a Supabase po ~ týždni — pred ukážkou 10 min vopred otvoriť (alebo free ping z cron-job.org).

## Kľúčové princípy

1. **Zubar-ve-slučke** — pri každom náleze tlačidlá *súhlasím / opraviť*. Zubár má kontrolu a zároveň sa buduje súkromný dataset na doladenie modelu na jeho prax.
2. **Súkromie** — pacienti pod kódmi (žiadne mená), privátny Space s heslom, dáta v EU/US cloud free tieru len na demo.
3. **Prezentácia:** AI = *druhý pohľad*, nie automatická diagnóza. Wow = overlay na jeho snímke + Grad-CAM + PDF report za minútu.

## Štruktúra

```
dental-ai-v2/
├── backend/            FastAPI + YOLO detektor + reporty
│   ├── app/
│   │   ├── main.py         /health, /analyze, /results, /report
│   │   ├── api/routes/      REST API endpoints
│   │   ├── core/           Autentifikácia, konfigurácia
│   │   └── ml/             ML pipeline
│   │       ├── detector.py      YOLOv8 detektor
│   │       ├── ensemble.py      Ensemble modelov
│   │       ├── sahi_detector.py SAHI (Slicing Aided Hyper Inference)
│   │       ├── tta.py           Test-Time Augmentation
│   │       ├── gradcam.py       Grad-CAM vizualizácia
│   │       ├── reporter.py      Generovanie PDF správ
│   │       ├── database.py      SQLite databáza
│   │       ├── calibration.py   Kalibrácia koeficientov
│   │       ├── anatomical.py    Anatomické mapovanie
│   │       ├── gemini_vision.py Google Gemini Vision API
│   │       └── preprocessor.py  Predspracovanie obrázkov
│   ├── tests/              Testy
│   └── requirements.txt
├── frontend/           React SPA
│   └── src/
│       ├── App.tsx              Hlavná aplikácia
│       ├── components/          UI komponenty
│       │   ├── UploadZone.tsx   Nahrávanie snímok
│       │   ├── Viewer.tsx       Zobrazovanie s detekciami
│       │   ├── FindingCard.tsx  Karta s nálezom
│       │   ├── MetricsPanel.tsx Metriky
│       │   └── Odontogram.tsx   Odontogram
│       └── lib/api.ts           API klient
├── demo/             Demo materiály (bez súkromných snímok)
│   ├── DEMO_SCENAR.md
│   └── DEMO_UI_VIZIA.html
├── docs/             Dokumentácia
│   ├── NOVY_PROJEKT_ASISTENT.md
│   ├── PLAN_2_DNI.md
│   ├── POROVNANIE.md
│   └── TRAINING_BUDGET.md
├── train/            Tréningové skripty (modely sú mimo gitu)
│   ├── train.py
│   ├── train_resume.py
│   ├── pseudolabel.py
│   ├── build_merged.py
│   ├── run_local_5h.py
│   ├── run_stage2_dentex.py
│   ├── supervise_night.py
│   ├── val_best.py
│   ├── kaggle_prep.py
│   ├── data.dentex.yaml
│   ├── data.mega5.yaml
│   └── class_map_mega.json
├── kaggle/night/     Kaggle kernely (modely sú mimo gitu)
│   ├── kernel-night.py
│   ├── kernel-v8l.py
│   ├── push_night.py
│   ├── carx/kernel-carx.py
│   ├── carxtest/test.py
│   ├── mega5/kernel-mega5.py
│   ├── merged/kernel-merged.py
│   └── v8l/kernel-v8l.py
├── Dockerfile          HF Spaces (port 7860)
└── docker-compose.yml  lokálny beh
```

## Kľúčové súčasti

### Backend (FastAPI)
- **ML Pipeline**: YOLOv8 detekcia → Ensemble → SAHI → TTA → Grad-CAM
- **19 tried patológií**: caries, periapical lesion, impacted tooth, bone loss, filling, crown, implant, root canal, pathology, etc.
- **API endpoints**:
  - `POST /api/analyze` — Analýza snímky
  - `GET /api/health` — Stav systému
  - `GET /api/results` — Výsledky
  - `GET /api/media` — Médiá
  - `POST /api/vision` — Gemini Vision
- **Autentifikácia**: Token-based
- **Databáza**: SQLite
- **PDF reporter**: Automatizované správy

### Frontend (React + Vite)
- Nahrávanie snímok (drag & drop)
- Zobrazovanie s detekciami (bounding boxes)
- Odontogram
- Metriky a štatistiky
- Dark theme

### Tréning
- **YOLOv8** (yolov8n, yolov8s, yolov8m, yolov8l)
- **Datasety**: DentEX, CariesX, Mega5, merged
- **Techniky**: Pseudolabeling, transfer learning, ensemble
- **Kaggle**: Tréning na Kaggle GPU (V100, T4)

## Štart lokálne (backend)

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Štart lokálne (frontend)

```bash
cd frontend
npm install
npm run dev
```

## Docker

```bash
docker-compose up --build
```

## Konfigurácia

Skopírujte `.env.example` do `.env` a vyplňte:
- `API_TOKEN` — Token pre API autentifikáciu
- `GEMINI_API_KEY` — Google Gemini API key (voliteľné)

## Hotové zdroje, ktoré projekt využíva

- Váhy: [NoahOksuz/DentalXrayAI](https://github.com/NoahOksuz/DentalXrayAI) `best.pt` (Apache-2.0) — 4 triedy: Caries, Deep Caries, Impacted, Periapical Lesion
- Dataset: [DENTEX](https://huggingface.co/datasets/ibrahimhamamci/DENTEX) (CC BY-NC-SA — len nekomerčne)
- Retréning: Kaggle GPU free (detaily v `docs/TRAINING_BUDGET.md`)

## Poznámky

- **Modely** (`.pt`, `.pth`, `.onnx`) sú príliš veľké pre Git a sú vylúčené
- **Pacientske dáta** (rentgenové snímky) sú súkromné a nikdy sa nedostanú do repozitára
- **Tréningové datasety** sú dostupné na Kaggle
- **Kaggle kernely** obsahujú tréningové skripty pre rôzne konfigurácie

## Licencia

MIT
