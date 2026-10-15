# 📊 Porovnanie: starý dental-ai vs. najnovšie OSS projekty vs. v2

**Dátum:** 5. október 2026 · Cieľ: profesionálne demo pre zubára na free hosting, vstavba za 2 dni.

## 1. Krajina podobných projektov (stav október 2026)

| Projekt | Model / triedy | UI | DB | Report | Feedback zubarom | Verdikt |
|---|---|---|---|---|---|---|
| **dental-ai (starý, náš)** | YOLOv8x, 19 tried (chaos), Caries mAP50 = 0.10, tréning prerušený | React — najbohatší (overlay, odontogram, Grad-CAM, PDF SK, merania mm) | SQLite lokálne | ✅ SK PDF | ❌ | Najlepšie UI, pokazený model + infra (venv rozbitý, 368 MB model na CPU pomalý) |
| [DentalXrayAI](https://github.com/NoahOksuz/DentalXrayAI) 46★ | YOLOv8n, 4 triedy DENTEX, mAP50 0.46, **hotové váhy** | jednoduchý Python server + HTML | ❌ | ❌ | ❌ | Ideálny **dárca váh**, nie produkt |
| [Dentection](https://github.com/valentinabc19/Dentection) | YOLOv8, 14 anomálií | Streamlit (španielsky) | ❌ | PDF (ES) | ❌ | Dobre zvolený rozsah tried, primitívna infra |
| [dental-xray-ai](https://github.com/abdubakr77/dental-xray-ai) | DENTEX 3-fázový: kvadrant → číslo zuba → diagnóza | notebooky | ❌ | ❌ | ❌ | Pattern pre FDI číslovanie — prevziať koncept |
| HF: [liodon-ai/dental-panoramic-detector](https://huggingface.co/liodon-ai/dental-panoramic-detector), [YOLO26 Dental](https://huggingface.co/EuricoGVP/YOLO26_Dental_Detection) | moderné detektory | — | — | — | — | Alternatívne váhy na benchmark |

**Záver:** nikto z OSS nemá produkt — majú model + minimálne UI. Nikto nemá DB, feedback loop, ani lokalizáciu. To je priestor v2.

## 2. Čo v2 konkrétne vylepšuje (vs. starý aj vs. OSS)

| # | Oblast | Starý dental-ai | v2 | Inšpirácia |
|---|---|---|---|---|
| 1 | **Model** | 19 tried (14 nefunkčných), Caries 0.10 | 4 triedy DENTEX, **hotové váhy mAP50 0.46 deň 1**, retrén podľa rozpočtu | DentalXrayAI |
| 2 | **Rýchlosť** | 368 MB YOLOv8x na CPU = sekundy až desiatky sekúnd | YOLOv8n/s, CPU inferencia 1–2 s; ONNX export (roadmap) pre 2–5× zrýchlenie | trend 2026: ONNX Runtime |
| 3 | **Infra** | lokálne SQLite, rozbitý venv (Python 3.12 zmizol) | čerstvý venv 3.11, Docker, **HF Spaces + Supabase Postgres** (dáta prežijú reštart) | — |
| 4 | **Feedback loop** | ❌ | **Súhlasím/Opraviť pri každom náleze + metriky zhody** — buduje súkromný dataset a dôveru | žiadny OSS to nemá → diferenciátor |
| 5 | **UI** | plné, ale „výskumné" | klinicky čisté: dark theme, conf slider, overlay, karty so závažnosťou, odontogram, Grad-CAM prepínač | moderné medical-AI dashboardy |
| 6 | **Súkromie** | nič | heslová brána, privátny Space, pacienti pod kódmi, anonymizácia | GDPR prax |
| 7 | **Dáta do modelu** | mega-dataset 5 tried (periapical 22 inštancií = mrtva trieda) | DENTEX 678/46/250 (čisté 4 triedy), neskôr + opravy zubara | DENTEX benchmark |

## 3. Inšpirácie z najnovších trendov (2026) — roadmap po demo

1. **Tooth-level FDI číslovanie** — 3-fázový prístup z dental-xray-ai (kvadrant → zub → diagnóza): kaz sa zobrazí „zub 36" nie „bbox vpravo dole".
2. **ONNX export** — Ultralytics `export(format="onnx")`, 2–5× rýchlejšia CPU inferencia na free tieri.
3. **VLM druhý názor** — Gemini Flash (free tier) napíše pacientske zhrnutie v slovenčine; koncept už existoval v starom `gemini_vision.py`.
4. **DICOM input** (pydicom) — zubárske prístroje exportujú DICOM, nie JPG.
5. **Roboflow hosted inference** — fallback detekcie bez vlastného GPU.
6. **YOLO26 váhy** (HF) — benchmark against v8s; ak recall na Caries vyšší, vymeniť.

## 4. Čo sa nemení (osvedčené zo starého projektu)

Grad-CAM heatmapy · SK PDF report pre pacienta · odontogram FDI · farebná závažnosť (urgent / treat soon / watch) · WebSocket progres (v2: na párty jednoduchý polling).
