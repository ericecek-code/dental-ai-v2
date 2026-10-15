# ⏱️ Časový rozpočet tréningu — 1080 Ti vs Kaggle

**Trénovací stroj (tento PC):** AMD Ryzen 5 2600, 40 GB RAM, **GTX 1080 Ti 11 GB** (overené nvidia-smi, driver 536.99).

**Datasety:**
- **DENTEX** (plne anotovaná časť): 705 train / 50 val / 250 test, 4 diagnózy — primárny pre demo
- **mega-dataset**: 7 228 train / 1 840 val, 5 tried — len pre Kaggle

---

## 1. Lokálny tréning na 1080 Ti

Charakteristika karty: Pascal architektúra, **žiadne tensor cores** → FP16/AMP nie je zrýchlený (Pascal má krpatý FP16, držať FP32, `amp=False`). Pevný bod: 11 GB VRAM a 40 GB RAM (väčšie batchy do RAM dajú `cache="disk"`).

### DENTEX (705 obrázkov) — odhad na 1 epochu / na 100 epôch

| Model | imgsz | batch (do 11 GB) | 1 epocha | 100 epôch | Kedy použiť |
|---|---|---|---|---|---|
| YOLOv8n | 640 | 12 | ~30 s | **~1 h** | sanity check pipeline — dnes večer |
| YOLOv8s | 1280 | 4–6 | ~4–5 min | **~7–9 h** | hlavný demo model — cez noc ✅ |
| YOLOv8m | 1280 | 3 | ~8–9 min | **~13–16 h** | víkendový run — najlepší lokálny |
| YOLOv8x | 1280 | 2 | ~15 min | ~25–30 h | neopodstatnené (pomalé, malý zisk) |

*Pripočítať ~15 % na validáciu, mozaiky a zápis. Tréning prežije spánok PC? Nie — nastaviť `nvidia-smi` vypnúť spánok, alebo nechať bežať cez deň.*

### mega-dataset (7 228 obrázkov) — lokálne NEKOMBITNÉ pri vyššom rozlíšení

| Model | imgsz | 1 epocha | 100 epôch | Verdikt |
|---|---|---|---|---|
| YOLOv8s | 640 | ~11–12 min | ~18–20 h | zvládnuteľné cez víkend |
| YOLOv8s | 1280 | ~43 min | ~72 h | ❌ |
| YOLOv8m | 1280 | ~1 h | ~4 dni | ❌ |

---

## 2. Kaggle (free) — P100 16 GB alebo 2× T4

Limity: **12 h / session**, **~30 h GPU / týždeň**. P100 ≈ 1,3× rýchlejší než 1080 Ti; 2× T4 s AMP ≈ 2–3× (T4 má tensor cores, AMP funguje). Session sa dá prerušiť a pokračovať `resume=True`.

| Run | 1 epocha | 100 epôch | Sessions | Verdikt |
|---|---|---|---|---|
| **s, DENTEX, 1280** (P100) | ~3–3,5 min | **~6 h** | 1 | ✅ bezpečne do 12 h |
| **m, DENTEX, 1280** (P100) | ~6–7 min | **~11 h** | 1 (tesne) / 2 s resume | ✅ odporúčaný hlavný run |
| s, mega, 640 (P100) | ~8 min | ~13–14 h | 2 s resume | ✅ ak chceme viac dát |
| m, mega, 640 (P100) | ~14 min | ~23 h | 2–3 s resume | ⚠️ večer spustiť |
| čokoľvek, mega, 1280 | ~30–45 min | 50–75 h | 5–7 | ❌ vyhorí týždenná kvóta |

Colab free (T4, ~12 h, nestály limit) = záložný variant s rovnakými číslami ako T4.

---

## 3. Odporúčaný harmonogram (rozpočet ~1 týždeň, beží na pozadí demo práce)

| Kedy | Čo | Kde | Čas |
|---|---|---|---|
| **Deň 1 večer** | sanity: YOLOv8n, DENTEX, 640, 100 ep | 1080 Ti | ~1 h |
| **Deň 1 noc** | hlavný demo model: YOLOv8s, DENTEX, 1280, 100 ep | 1080 Ti | ~8 h (ráno hotovo) |
| **Deň 2** | demo beží s novými váhami; spustiť YOLOv8m, DENTEX, 1280 | Kaggle P100 | ~11 h na pozadí |
| **Deň 3–4** | porovnať s vs m (mAP50, recall na Caries); lepší do Space-u | — | 1 h práce |
| **Víkend** (voliteľné) | m alebo s, mega-dataset, 640 — viac dát, 2 sessions s resume | Kaggle | ~14–23 h |

**Očakávaný výstup:** mAP50 ~0.45–0.6 na 4 triedy, po tuningu prahu recall na Caries ≥ 0.6–0.75 — na demo a wow efekt postačuje. Ďalší skok dá až zubar-ve-v-slučke dataset (jeho snímky, jeho opravy).

---

## 4. Praktické poznámky pre 1080 Ti

- **PyTorch:** Pascal (sm_61) je legacy — použiť wheel `cu118`/`cu121`; starý venv v dental-ai je rozbitý (odkazuje na odinštalovaný Python 3.12), v2 staviť na čerstvý venv (Python 3.11).
- `amp=False` (FP16 na Pascale pomalšie), `workers=8`, `cache="disk"` (RAM stačí, ale disk je bezpečnejší), `patience=30`, `device=0`.
- Batch pri 1280 px držať 3–6 podľa modelu; pri CUDA OOM znížiť batch, nie imgsz.
- Kaggle: dataset nahrať **aj s `data.yaml` v koreni** (práve tohto sa minule v starom projekte dopustila chyba) a v notebooku `resume=True` na prerušenie.
