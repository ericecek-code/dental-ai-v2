# 🗓️ Plán výstavby — 2 dni + paralelný tréning

## Deň 1 — reťazec end-to-end beží

| # | Úloha | Výstup |
|---|---|---|
| 1 | Scaffold monorepa (✅ hotové), frontend `npm create vite` + Tailwind | štruktúra |
| 2 | Supabase projekt (UI), schéma: `patients`, `analyses`, `findings` | `DATABASE_URL` do `.env` |
| 3 | Backend: `/analyze` detekcia (✅ stub hotový) + zápis do DB + Storage | JSON s nálezmi |
| 4 | Frontend: UploadZone → viewer s overlayom → karty nálezov | základ UI |
| 5 | Stiahnuť `best.pt` do `backend/weights/` (Apache-2.0) | funkčná detekcia |
| 6 | Večer: deploy v1 na HF Spaces; spustiť sanity tréning n@640 lokálne (~1 h) | verejná URL |

## Deň 2 — wow vrstva

| # | Úloha | Výstup |
|---|---|---|
| 7 | Tlačidlá Súhlasím/Opraviť pri náletoch → `findings.status` | zubar-ve-v-slučke |
| 8 | Pacientsky PDF report (ReportLab, 1 strana, SK) + odontogram-lite SVG | PDF za minútu |
| 9 | Grad-CAM heatmapa v vieweri | wow moment |
| 10 | Heslová brána, privátny Space, anonymizácia (kódy namiesto mien) | súkromie |
| 11 | Demo balík: 10 overených prípadov + scenár stretnutia | pripravené demo |
| 12 | Noc: Kaggle run YOLOv8m, DENTEX, 1280 (~11 h, resume) — detaily v TRAINING_BUDGET.md | lepší model ráno |

## Po demo (týždeň 2)

- Vymeniť váhy za najlepší Kaggle model, zmerať recall na Caries na jeho prípadoch.
- Metriky zhody (view nad `findings`) — po ~30 prípadoch ukázať „AI súhlasí s vami v X %".
- Ping cron-job.org proti zaspávaniu; záloha DB (Supabase dump raz týždenne).

## Ešte neurobené (vedome)

- Multi-user auth, DICOM native, PACS, CE certifikácia — pre súkromné demo netreba.
- Komerčné použitie — bráni licencia DENTEX (CC BY-NC-SA).
