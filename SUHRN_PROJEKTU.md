# 📋 SÚHRN PROJEKTU pre supervízora — Dental AI v2

*PI-Desktop, 2026-10-10. Plný detail: `POPIS_PROJEKTU.md` · Tréning: `KAGGLE_PRIRUCKA_PRE_AGENTOV.md` · Porovnanie v1/v2: `docs/POROVNANIE.md`.*

## Stav v jednej vete

**Dental AI v2 je funkčný hotový demo-projekt (verzia ~85–90 %)** — chýba len deploy na Hugging Face Spaces (čaká na HF_TOKEN), oprava známych bugov a zapojenie zubára do feedback loopu. Starý `dental-ai` (v1) je opustená experimentálna skládka (Caries mAP50 0,10 vs. náš 0,61) — na ňom sa nepokračuje.

## Momentálna presnosť (overené na čistom DENTEX valid: 46 snímok, 182 nálezov)

| Čo | Hodnota | Výklad |
|---|---|---|
| **Celková presnosť detekcie (mAP50)** | **61,0 %** | nájdenie a presné ohraničenie nálezov |
| **Citlivosť na kaz (Caries recall)** | **72,3 %** | z 10 kazov nájde ~7 — úroveň lekára s 1–3 rokmi praxe |
| Plomba (restaurácie, mega5 model) | **92 %** | najspoľahlivejšia trieda |
| Retinovaný zub (Impacted) | 85,8 % | |
| Periapická lézia / hlboký kaz | 48 % / 53 % | najťažšie triedy — treba viac čistých dát |

**Kontext:** komerčná špička (Overjet, Pearl — FDA certifikát) dosahuje 85–95 %, ale stojí 200–500 $/mesiac a potrebuje milióny snímok. Skúsený zubár (15 rokov) nájde ~75–85 % — **projekt ho nenahrádza, ale je sieť pod ním**: v štúdiách lekári aj s horšou AI našli kaz, ktorý sami prehliadli, v ~1 z 5–6 prípadov. Modelový strop na verejných dátach je dosiahnutý — ďalšie percentá prídu od zubára (jeho 30–200 označkovaných prípadov = +5–10 pp na jeho prístroji).

## Čo všetko potrebujeme vylepšiť (prioritný zoznam)

### P1 — kritické (pred akoukoľvek ukážkou klientom)
1. **Blokujúca analýza zamrzne server** — `backend/app/api/routes/analyze.py:25`: `async def` volá CPU inferenciu (5–10 s) v event loope → počas analýzy neodpovie ani `/health`. Oprava: `def analyze` alebo `run_in_executor`.
2. **Pacientske dáta a tajomstvo v gite** — 112 súborov (RTG s menami, PDF, `db.sqlite`, `backend/data/.secret` HMAC kľúč). Oprava: `git rm --cached` + `.gitignore` + rotovať secret + prečistiť históriu (`git filter-repo`).
3. **PDF bez slovenskej diakritiky v produkcii** — `reporter.py` načíta len Windows fonty; v Linux kontajneri fallback Helvetica bez č/š/ž. Oprava: DejaVu Sans do kontajnera.
4. **Deploy nefunkčný** — chýba `.dockerignore` (COPY vtiahne 4,9 GB `.venv`), `Dockerfile` kopíruje `frontend/dist` a váhy, ktoré sú v `.gitignore`. Oprava: .dockerignore + multi-stage build + váhy počas buildu.

### P2 — dôležité (správnosť AI funkcií)
5. **TTA rotácie ±90° nefungujú** — `detector.py _transform_bbox` má prehodené orig_w/orig_h → 2 z 5 augmentácií vygenerujú boxy mimo snímky. Anatomicky aj tak nezmyselné — radšej vypnúť (nechať hflip + škály + CLAHE).
6. **MC Dropout neistota = 0,0 pri všetkých 153 nálezoch** — zlučovanie podľa presného bbox + `model.eval()` v predicte. Oprava: párovanie cez IoU ≥ 0,5 + inferencia v train režime.
7. **Duplicitné definície** `_nms_per_class`/`_weighted_box_fusion` v detector.py (2×) — druhá ticho prepíše prvú.
8. **Webová vrstva**: CORS `*`, cookie bez `secure`, 401 maskuje 404 (`.mcp` spam v logoch), DICOM sľúbený v UI ale nečítaný, uploady sa nikdy nemazú.

### P3 — rast presnosti a hodnoty
9. **Feedback loop u zubára** — zapnúť Súhlasím/Opraviť → 30–200 označkovaných prípadov = **+5–10 pp** fine-tuningom na jeho prístroji. To je hlavná cesta nahor.
10. **Pre-training na mega-datasete** → finetuning na čistom DENTEX (+1–3 pp) — postup v Kaggle príručke (NIEMIEŠAŤ značky priamo — 3 experimenty potvrdili pokles).
11. **ONNX export** (2–5× rýchlejšia CPU inferencia na free tieri), **FDI číslovanie zuba** („kaz na zube 36"), **VLM druhý názor** (Gemini Flash — pacientske zhrnutie), **DICOM input** (pydicom — prístroje exportujú DICOM, nie JPG), **YOLO26 váhy benchmark**.

## Náklady a prevádzka

**0 €/mesiac**: HF Spaces free (CPU) + Supabase free (500 MB DB + 1 GB storage) + Kaggle free GPU (~18 h ostáva). Slabina free tieru: Space zaspí po 48 h nečinnosti — pred ukážkou otvoriť vopred (alebo free ping z cron-job.org). Kaggle kvóta sa má míňať rozumne (detaily v príručke).

## Synergia

Rovnaký backend vzor a login je pripravený pre **AI Recepnú** (`docs/NOVY_PROJEKT_ASISTENT.md`): pacient prijíma 24/7 (Viber bot 0–5 €/mes, neskôr hlasový agent), rezervácie termínov bez telefónovania. Spoločný príbeh: „AI v ambulancii od A do Z" — recepná prijíma, AI pomáha lekárovi s RTG.
