"""Kaggle prep: upload merged dataset + vytvorenie a push treningoveho kernelu.
Spustit PO builde merged datasetu (train/runs/merged/data.merged.yaml existuje).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

VENV = Path(r"C:\Users\PC1\Desktop\dental-ai-v2\backend\.venv\Scripts")
MERGED = Path(r"C:\Users\PC1\Desktop\dental-ai-v2\train\runs\merged")
KAGGLE_DIR = Path(r"C:\Users\PC1\Desktop\dental-ai-v2\kaggle_merged")
DS_SLUG = "eriksmite/dental-merged-v1"
KERNEL_SLUG = "eriksmite/dental-merged-v1-training"

NB = r'''
!pip install -q ultralytics

import json, time
from ultralytics import YOLO

DATA = "/kaggle/input/dental-merged-v1/data.merged.yaml"
# path v data.merged.yaml ukazuje lokalne — na Kaggle prepisat relativne na input root
import yaml, shutil
cfg = yaml.safe_load(open(DATA))
cfg["path"] = "/kaggle/input/dental-merged-v1"
yaml.safe_dump(cfg, open("/kaggle/working/data_kaggle.yaml", "w"), sort_keys=False)

model = YOLO("/kaggle/input/dental-merged-v1/weights/best.pt")  # fine-tune z nocneho best
model.train(
    data="/kaggle/input/dental-merged-v1/data_kaggle.yaml",
    epochs=120, time=9, imgsz=1280, batch=8, device=0,
    project="/kaggle/working", name="merged_v1",
    patience=20, optimizer="AdamW", lr0=0.0005, cos_lr=True,
    flipud=0.0, fliplr=0.5, mosaic=1.0, close_mosaic=10,
)
best = "/kaggle/working/merged_v1/weights/best.pt"
m = YOLO(best).val(data="/kaggle/input/dental-merged-v1/data_kaggle.yaml")
print("FINAL mAP50:", m.box.map50)
for i, c in enumerate(m.box.ap_class_index):
    print("class", int(c), "ap50:", float(m.box.ap50[i]))
shutil.copy2(best, "/kaggle/working/best_merged.pt")
print("OK best_merged.pt ulozeny")
'''

def run(cmd):
    print(">>>", " ".join(cmd[:3]), "...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = (r.stdout or "") + (r.stderr or "")
    print(out[-1500:] if len(out) > 1500 else out)
    if r.returncode != 0:
        print(f"EXIT {r.returncode}")
    return r.returncode, out

def main():
    step = sys.argv[1] if len(sys.argv) > 1 else "all"

    if step in ("dataset", "all"):
        KAGGLE_DIR.mkdir(parents=True, exist_ok=True)
        meta = {"title": "dental-merged-v1", "id": DS_SLUG, "licenses": [{"name": "other"}]}
        # obsah: merged train+val+yaml+weights
        import shutil
        dst = KAGGLE_DIR / "payload"
        if dst.exists():
            shutil.rmtree(dst)
        dst.mkdir()
        (dst / "dataset-metadata.json").write_text(json.dumps(meta))
        shutil.copytree(MERGED / "train", dst / "train")
        shutil.copytree(MERGED / "val", dst / "val")
        shutil.copy2(MERGED / "data.merged.yaml", dst / "data.merged.yaml")
        w = dst / "weights"
        w.mkdir()
        shutil.copy2(r"C:\Users\PC1\Desktop\dental-ai-v2\backend\weights\best.pt", w / "best.pt")
        # fix yaml path → relativny
        y = dst / "data.merged.yaml"
        y.write_text(y.read_text(encoding="utf-8").replace(str(MERGED.resolve()), "/kaggle/input/dental-merged-v1"), encoding="utf-8")
        rc, _ = run([str(VENV / "kaggle.exe"), "datasets", "create", "-p", str(dst), "--dir-mode", "zip"])
        if rc != 0:
            print("DATASET CREATE FAIL"); sys.exit(1)

    if step in ("kernel", "all"):
        import nbformat as nbf
        nb = nbf.v4.new_notebook()
        nb.cells = [nbf.v4.new_code_cell(NB)]
        kd = KAGGLE_DIR / "kernel"
        kd.mkdir(exist_ok=True)
        nb.metadata.kernelspec = {"display_name": "Python 3", "language": "python", "name": "python3"}
        (kd / "notebook.ipynb").write_text(nbf.writes(nb), encoding="utf-8")
        meta = {
            "id": KERNEL_SLUG,
            "title": "Dental merged v1 training",
            "code_file": "notebook.ipynb",
            "language": "python",
            "kernel_type": "notebook",
            "is_private": True,
            "enable_gpu": True,
            "enable_internet": True,
            "dataset_sources": [DS_SLUG],
            "kernel_sources": [],
        }
        (kd / "kernel-metadata.json").write_text(json.dumps(meta, indent=1))
        rc, _ = run([str(VENV / "kaggle.exe"), "kernels", "push", "-p", str(kd)])
        if rc != 0:
            print("KERNEL PUSH FAIL"); sys.exit(1)
        print("KERNEL PUSHNUTY:", KERNEL_SLUG)

if __name__ == "__main__":
    main()

