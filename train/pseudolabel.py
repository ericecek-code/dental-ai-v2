"""Pseudolabeling / cross-labeling pipeline pre Fázu 0 (ciel: Caries recall 78 %).

Mody:
  cross — existujuce GT anotacie: nechaj LEN taku anotaciu, s ktorou Suhlasi aj model
          (rovnaka trieda + IoU >= 0.5) → ciste alabely (poucenie zo 3 zlyhanych experimentov)
  pseudo — unlabeled snimky: model generuje labely (conf >= --conf)

Pouzitie (venv):
  python train/pseudolabel.py --images <dir> --labels <dir> --out <dir> \
      --mode cross --map train/class_map_mega.json [--conf 0.5] [--limit 50]
Vystup: YOLO txt (class cx cy w h) normalizovane; nazov = nazov obrazku.
"""
import argparse
import json
from pathlib import Path

import numpy as np

CLASSES = ["Impacted", "Caries", "Periapical Lesion", "Deep Caries"]  # DENTEX ids 0..3
IMG_EXTS = {".jpg", ".jpeg", ".png", ".JPG", ".PNG"}


def iou_xyxy(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    if inter == 0:
        return 0.0
    area = lambda s: max(0, s[2] - s[0]) * max(0, s[3] - s[1])
    return inter / (area(a) + area(b) - inter + 1e-9)


def yolo_to_xyxy(cxcywh, w, h):
    cx, cy, bw, bh = cxcywh
    return [ (cx - bw/2)*w, (cy - bh/2)*h, (cx + bw/2)*w, (cy + bh/2)*h ]


def xyxy_to_yolo(box, w, h):
    return [ (box[0]+box[2])/2/w, (box[1]+box[3])/2/h, (box[2]-box[0])/w, (box[3]-box[1])/h ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True)
    ap.add_argument("--labels", default=None, help="GT labely (YOLO txt) pre cross mode")
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", choices=["cross", "pseudo"], required=True)
    ap.add_argument("--map", default=None, help="JSON {gt_class_id: dentex_class_id alebo null=skip}")
    ap.add_argument("--conf", type=float, default=0.5)
    ap.add_argument("--iou", type=float, default=0.5)
    ap.add_argument("--limit", type=int, default=0, help="smoke test: max obrazkov")
    ap.add_argument("--weights", default="weights/best.pt")
    args = ap.parse_args()

    mapping = None
    if args.map:
        mapping = {int(k): v for k, v in json.loads(Path(args.map).read_text(encoding="utf-8-sig")).items()}

    images_dir = Path(args.images)
    imgs = sorted([p for p in images_dir.rglob("*") if p.suffix in IMG_EXTS])
    if args.limit:
        imgs = imgs[: args.limit]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    from ultralytics import YOLO
    import torch
    model = YOLO(args.weights)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"model={args.weights} device={device} mode={args.mode} obrazkov={len(imgs)}", flush=True)

    kept = skipped = nimg = 0
    for i, img_path in enumerate(imgs):
        # cross mode: preskoc (bez drahej inferencie) snimky, ktore nemaju ziadnu
        # GT triedu po mapovani (napr. len Crown/Filling/Implant)
        if args.mode == "cross":
            pre = None
            if args.labels:
                cand = Path(args.labels) / (img_path.stem + ".txt")
                if cand.exists():
                    pre = cand
                else:
                    hits = list(Path(args.labels).rglob(img_path.stem + ".txt"))
                    pre = hits[0] if hits else None
            relevant = False
            if pre is not None:
                for line in pre.read_text().strip().splitlines():
                    parts = line.split()
                    if len(parts) != 5:
                        continue
                    g = int(parts[0])
                    m = mapping.get(g, g) if mapping else g
                    if m is not None:
                        relevant = True
                        break
            if not relevant:
                skipped += 1
                continue

        res = model.predict(str(img_path), conf=args.conf, imgsz=1280, device=device, verbose=False)[0]
        h, w = res.orig_shape
        preds = []
        for b in res.boxes:
            preds.append((int(b.cls), [float(v) for v in b.xyxy[0].tolist()], float(b.conf)))

        lines = []
        if args.mode == "pseudo":
            for cls, box, _c in preds:
                cx, cy, bw, bh = xyxy_to_yolo(box, w, h)
                lines.append(f"{cls} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
        else:  # cross
            lbl_path = None
            if args.labels:
                cand = Path(args.labels) / (img_path.stem + ".txt")
                if cand.exists():
                    lbl_path = cand
                else:  # hladaj v sub adresari podla mena (mega: labels/train/... )
                    hits = list(Path(args.labels).rglob(img_path.stem + ".txt"))
                    lbl_path = hits[0] if hits else None
            if lbl_path is None:
                skipped += 1
                continue
            for line in lbl_path.read_text().strip().splitlines():
                parts = line.split()
                if len(parts) != 5:
                    continue
                gt_cls_raw = int(parts[0])
                gt_cls = mapping.get(gt_cls_raw, None) if mapping else gt_cls_raw
                if gt_cls is None:
                    continue
                gt_box = yolo_to_xyxy([float(x) for x in parts[1:]], w, h)
                ok = any(p[0] == gt_cls and iou_xyxy(gt_box, p[1]) >= args.iou for p in preds)
                if ok:
                    cx, cy, bw, bh = xyxy_to_yolo(gt_box, w, h)
                    lines.append(f"{gt_cls} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

        (out_dir / (img_path.stem + ".txt")).write_text("\n".join(lines) + ("\n" if lines else ""))
        kept += len(lines)
        nimg += 1
        if (i + 1) % 200 == 0:
            print(f"  {i+1}/{len(imgs)} | labelov={kept} | preskocenych_img={skipped}", flush=True)

    print(f"HOTOVO: {nimg} obrazkov, {kept} labelov, preskocenych (bez GT) {skipped} → {out_dir}", flush=True)


if __name__ == "__main__":
    main()
