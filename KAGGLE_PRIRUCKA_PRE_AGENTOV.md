# ☁️ Kaggle príručka pre budúcich agentov — tréning Dental AI

*Vytvorené PI-Desktop 2026-10-10 (dokument dorobený namiesto ZCode session `sess_d3a979f8`). Zdroje: v1 `KAGGLE_INSTRUCTIONS_FOR_AGENT.md`, ZCode session (chyby z prvého pripojenia), v2 `train/` + `kaggle_kernel/`, `DATASET_DEDUPE_MAP.md`.*

## 1. Konto a prístupy

- **Kaggle username:** `eriksmite`
- **API kľúč:** `C:\Users\PC1\.kaggle\kaggle.json` (používateľ ho poskytuje na požiadanie)
- **Kaggle kvóta:** po tréningoch 4.–6.10. ostáva **~18 hodín GPU** — minimalizovať behy!
- Používateľ vie poskytnúť aj prihlásenie do **Roboflow** (hosted inference fallback).

## 2. Štyri chyby z prvého tréningu (v1) — NAOPAKOVAŤ!

### Chyba 1: Read-only file system
```
OSError: [Errno 30] Read-only file system: '/kaggle/input/.../data.yaml'
```
`/kaggle/input/` je read-only. **Riešenie:** skopírovať dataset do `/kaggle/working/` pred akoukoľvek modifikáciou:
```python
import shutil
shutil.copytree("/kaggle/input/mega-dataset-dental/mega-dataset", "/kaggle/working/dataset")
DATASET_PATH = "/kaggle/working/dataset"
```

### Chyba 2: Dataset je nested (vnořený)
```
FileNotFoundError: '/kaggle/input/mega-dataset-dental/data.yaml' does not exist
```
Skutočná cesta je **`/kaggle/input/mega-dataset-dental/mega-dataset/data.yaml`** (dvojitý nesting). Vždy overiť `os.listdir` pred tréningom.

### Chyba 3: CUDA incompatibilita (Tesla P100)
```
CUDA error: no kernel image is available for execution on the device
```
Tesla P100 (CUDA 6.0) nie je kompatibilná s aktuálnym PyTorch na Kaggle. **Riešenie:** vyberať accelerator **T4/P100→ nie** — použiť **GPU T4 x2** alebo **Colab T4**; lokálna GTX 1080 Ti funguje (overené — v8s night tréning bežal lokálne).

### Chyba 4: nbformat null
```
Error converting value {null} to type 'System.Int32'. Path 'nbformat'
```
Neplatný notebook JSON. **Riešenie:** vytvárať notebook cez `nbformat` knižnicu (v2 to rieši generátor `create_notebook.py`).

## 3. Overený postup v2 (aktuálny kernel)

- **Kernel:** `eriksmite/dental-yolov8-training-v5` (YOLOv8m, 5 tried, 100 epoch, imgsz 1280, batch 6, dataset `eriksmite/mega-dataset-dental`)
- **Lokálne súbory:** `dental-ai-v2/kaggle_kernel/notebook.ipynb` + `kernel-metadata.json`
- **Generátor notebooku:** `create_notebook.py` (v koreni v2) — uprav konfiguráciu TU a pregeneruj
- **Push na Kaggle:** `download_kernel.py` / `download_kernel_api.py` / `download_kernel_http.py` (v koreni v2 — skripty na push/stiahnutie výstupov)
- **Čakanie na beh:** `wait_for_kernel.ps1` / `wait_for_kernel_training.ps1` (polling kernel statusu)
- **Stiahnutie + validácia:** výstupy do `kernel_output*/`, validácia cez `train/val_best.py`

⚠️ **Pozor — známy bug validácie:** `val_best.py` na lokálnej validácii **timeoutuje po 900 s** (MORNING_REPORT 5.10.) — spúšťať s dlhším timeoutom alebo validovať priamo na Kaggle v notebooku (split=valid/test).

## 4. Datasety (central kópie — NE kopírovať duplicitne!)

| Dataset | Kde (central) | Veľkosť | Použitie |
|---|---|---|---|
| `mega-dataset-dental` (5 tried, 7 228/1 840/1 103) | zip: `dental-ai\mega-dataset.zip` (SHA256 DB41…E0D8), upload na Kaggle hotový | 741 MB | restaurácie (mega5) + pre-training |
| DENTEX (4 čisté triedy, 678/46/250) | `dental-ai\datasets\dentex\DENTEX\training_data.zip` (10,9 GB); `dental-ai-v2\kaggle\night\dentex_night.zip` (3,8 GB) | 3,8–10,9 GB | **hlavný tréning** (čisté konvencie) |
| dentex_training_sample_hashes | `dental-ai-v2\dentex_training_sample_hashes.txt` + `DATASET_DEDUPE_MAP.md` | — | dedupe kontrola |

**Pravidlo:** budúce ťažké datasety do `dental-ai\archive\`, v varianty cez NTFS junctions (symlink vyžaduje admin; junction nie).

## 5. Konfigurácia tréningu (osvedčené)

```python
CONFIG = {
    "model": "yolov8s.pt",          # v8s = hlavný (rýchly, 22 MB); v8m = donor/ensemble
    "data": "<working>/data.yaml",
    "epochs": 50,                    # VYDALENÉ: 50 stačí (peak ~epoche 26-48); user: "len nutný počet epoch"
    "imgsz": 1280,                   # panoramatické RTG — 1280 overené
    "batch": 6,                      # pri imgsz 1280 na 1080 Ti
    "patience": 15,
    "optimizer": "AdamW", "lr0": 0.001, "cos_lr": True,
    "flipud": 0.0,                   # ⚠️ ŽIADNY vertikálny flip — anatomicky nezmyselný
    "fliplr": 0.5,                   # horizontálny flip OK
    # ⚠️ ŽIADNE ±90° rotácie — zobrazujú zuby hore nohami (backend má navyše bug v _transform_bbox)
    "mosaic": 1.0, "mixup": 0.1, "close_mosaic": 10,
}
```

**Výsledok na čistom DENTEX valid (overené):** mAP50 61,0 % · Caries recall 72,3 % · Impacted 85,8 %.

## 6. Poučenia zo session (kritické — čítať pred každým tréningom!)

1. **Nemiešať externé značky s DENTEX konvenciami** — 3 experimenty potvrdili: merged DENTEX+mega (−32,7 pp Caries recall), CariesX (+0,9 pp celok, ale recall 72→42). Dôvod: mega „Caries" mieša bežný + hlboký kaz, značkovali ho iní ľudia na iných prístrojoch.
2. **Správne využitie mega-datasetu:** pre-training na mega → finetuning na čistom DENTEX (+1–3 pp); alebo cross-labeling (model označkuje, použijem len zhody s AI → 7 000+ čistých kazov).
3. **Modelový strop bez čistých dát je dosiahnutý** — ďalšie reálne percentá prídu od zubára (jeho 30–200 označkovaných prípadov = +5–10 pp na jeho prístroji).
4. **Minimalizovať GPU čas** — kvóta ~18 h; supervízor (`train/supervise_night.py`) stráži behy lokálne.
5. **Pred behom overiť:** accelerator (T4), nested cestu, read-only input, validáciu v notebooku (nie lokálne val_best.py bez dlhšieho timeoutu).
