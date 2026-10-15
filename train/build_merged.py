"""Build merged dataset pre Fázu 0 (ciel Caries recall 78 %).

Zdroje (JSON konfiguracia --config):
  - typ yolo: images dir + labels dir (cross/pseudo labely, DENTEX ids uz aplikovane)
  - typ coco: COCO json (polygon/RLE/bbox) + images root + {category_name: dentex_id} mapa (case-insensitive)
  - typ voc:  annotations dir (Pascal VOC bndbox ALEBO LabelMe XML polygon) + images dir + mapa

val = DENTEX val NEDOTKNUTY (fair eval). Vsetky images dostanu prefix zdroja.
Vystup: <out>/train/{images,labels}, <out>/val/{images,labels}, data.merged.yaml (nc=4).
"""
import argparse
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

import yaml

DENTEX = Path(r"C:\Users\PC1\Desktop\dental-ai\datasets\dentex")
IMG_EXTS = {".jpg", ".jpeg", ".png"}


def make_lut(name_to_id):
    return {k.strip().lower(): v for k, v in (name_to_id or {}).items()}


def coco_to_yolo_rows(json_path: Path, name_to_id: dict):
    lut = make_lut(name_to_id)
    data = json.loads(json_path.read_text(encoding="utf-8-sig"))
    cat_by_id = {c["id"]: c["name"] for c in data.get("categories", [])}
    img_by_id = {i["id"]: i for i in data.get("images", [])}
    per_img = {}
    for ann in data.get("annotations", []):
        cls_name = cat_by_id.get(ann.get("category_id"))
        target = lut.get((cls_name or "").strip().lower())
        if target is None:
            continue
        img = img_by_id.get(ann.get("image_id"))
        if img is None:
            continue
        w, h = img["width"], img["height"]
        seg = ann.get("segmentation")
        # polygon (list of lists) → bbox; RLE dict / ine → bbox zo "bbox" pola
        if isinstance(seg, list) and seg and isinstance(seg[0], list):
            xs, ys = seg[0][0::2], seg[0][1::2]
            x1, x2, y1, y2 = min(xs), max(xs), min(ys), max(ys)
        else:
            x, y, bw, bh = ann["bbox"]
            x1, y1, x2, y2 = x, y, x + bw, y + bh
        cx, cy = (x1 + x2) / 2 / w, (y1 + y2) / 2 / h
        rows = per_img.setdefault(img["file_name"], [])
        rows.append(f"{target} {cx:.6f} {cy:.6f} {(x2 - x1) / w:.6f} {(y2 - y1) / h:.6f}")
    return per_img  # file_name → [yolo lines]


def _txt_int(el):
    """int() z textu elementu; None ak element chyba alebo je prazdny (napr. <nrows />)."""
    if el is None or el.text is None or not el.text.strip():
        return None
    try:
        return int(float(el.text))
    except ValueError:
        return None


def voc_or_labelme_to_yolo_rows(ann_dir: Path, name_to_id: dict, imgs_root: Path | None = None):
    """Pascal VOC (bndbox) aj LabelMe XML (polygon points → bbox); case-insensitive mapa."""
    lut = make_lut(name_to_id)
    per_img = {}
    for xml in sorted(ann_dir.rglob("*.xml")):
        try:
            root = ET.parse(xml).getroot()
        except ET.ParseError:
            continue
        rows = []
        size = root.find("size")
        w, h = (None, None)
        if size is not None:
            w, h = _txt_int(size.find("width")), _txt_int(size.find("height"))
        if w is None or h is None:
            isz = root.find("imagesize")
            if isz is not None:
                w2, h2 = _txt_int(isz.find("ncols")), _txt_int(isz.find("nrows"))
                if w2 is not None and h2 is not None:
                    w, h = w2, h2
        if w is None or h is None:
            w3, h3 = _txt_int(root.find("imageWidth")), _txt_int(root.find("imageHeight"))
            if w3 is not None and h3 is not None:
                w, h = w3, h3
        if w is None or h is None:
            # LabelMe s prazdnymi <nrows /> <ncols /> -> rozmer citaj z obrazka (PIL)
            fn0 = root.find("filename")
            guess = fn0.text if fn0 is not None and fn0.text else xml.stem + ".jpg"
            ip = resolve_image(imgs_root, guess) if imgs_root is not None else None
            if ip is None:
                continue  # bez rozmeru nemozno normalizovat
            try:
                with Image.open(ip) as im:
                    w, h = im.size
            except Exception:
                continue
        for obj in root.iter("object"):
            name_el = obj.find("name")
            cls_name = (name_el.text or "").strip() if name_el is not None else ""
            target = lut.get(cls_name.lower())
            if target is None:
                continue
            bnd = obj.find("bndbox")
            if bnd is not None:
                x1, y1 = float(bnd.find("xmin").text), float(bnd.find("ymin").text)
                x2, y2 = float(bnd.find("xmax").text), float(bnd.find("ymax").text)
            else:
                poly = obj.find("polygon")
                if poly is None:
                    continue
                xs = [float(p.find("x").text) for p in poly.iter("pt") if p.find("x") is not None]
                ys = [float(p.find("y").text) for p in poly.iter("pt") if p.find("y") is not None]
                if not xs or not ys:
                    continue
                x1, x2, y1, y2 = min(xs), max(xs), min(ys), max(ys)
            if x2 - x1 < 2 or y2 - y1 < 2 or w <= 0 or h <= 0:
                continue
            rows.append(f"{target} {(x1+x2)/2/w:.6f} {(y1+y2)/2/h:.6f} {(x2-x1)/w:.6f} {(y2-y1)/h:.6f}")
        fn_el = root.find("filename")
        fn = (fn_el.text if fn_el is not None and fn_el.text else xml.stem + ".jpg")
        per_img[fn] = rows
    return per_img


def resolve_image(imgs_root: Path, fn: str) -> Path | None:
    p = imgs_root / fn
    if p.exists() and p.suffix.lower() in IMG_EXTS:
        return p
    hits = [h for h in imgs_root.rglob(Path(fn).stem + ".*")
            if h.is_file() and h.suffix.lower() in IMG_EXTS]
    return hits[0] if hits else None


def add_yolo_pair(src_img: Path, yolo_lines: list[str], out_split: Path, prefix: str):
    dst_img = out_split / "images" / f"{prefix}_{src_img.name}"
    shutil.copy2(src_img, dst_img)
    (out_split / "labels" / (dst_img.stem + ".txt")).write_text(
        "\n".join(yolo_lines) + ("\n" if yolo_lines else ""), encoding="utf-8"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8-sig"))
    out = Path(args.out)
    if out.exists():
        print(f"CHYBA: {out} uz existuje")
        return
    train_dir = out / "train"
    val_dir = out / "val"
    for d in (train_dir, val_dir):
        (d / "images").mkdir(parents=True)
        (d / "labels").mkdir(parents=True)

    stats = {}

    # 1) DENTEX train (kanonicky, 1:1) + val = eval set (nedotknuty)
    n = 0
    for img in sorted((DENTEX / "images" / "train").rglob("*")):
        if img.suffix.lower() not in IMG_EXTS:
            continue
        lbl = DENTEX / "labels" / "train" / (img.stem + ".txt")
        shutil.copy2(img, train_dir / "images" / f"dentex_{img.name}")
        if lbl.exists():
            shutil.copy2(lbl, train_dir / "labels" / f"dentex_{img.stem}.txt")
        n += 1
    stats["dentex_train"] = n
    nv = 0
    for img in sorted((DENTEX / "images" / "val").rglob("*")):
        if img.suffix.lower() not in IMG_EXTS:
            continue
        lbl = DENTEX / "labels" / "val" / (img.stem + ".txt")
        shutil.copy2(img, val_dir / "images" / f"dentex_{img.name}")
        if lbl.exists():
            shutil.copy2(lbl, val_dir / "labels" / f"dentex_{img.stem}.txt")
        nv += 1
    stats["dentex_val(=eval)"] = nv

    # 2) dalsie zdroje
    for src in cfg.get("sources", []):
        typ, prefix = src["type"], src["prefix"]
        try:
            if typ == "yolo":
                lbls_root = Path(src["labels"])
                cnt = 0
                for img in sorted(Path(src["images"]).rglob("*")):
                    if img.suffix.lower() not in IMG_EXTS:
                        continue
                    lbl = lbls_root / (img.stem + ".txt")
                    if not lbl.exists():
                        continue
                    lines = [l for l in lbl.read_text().strip().splitlines() if l.strip()]
                    if not lines:
                        continue
                    add_yolo_pair(img, lines, train_dir, prefix)
                    cnt += 1
                stats[prefix] = cnt
            elif typ == "coco":
                per_img = coco_to_yolo_rows(Path(src["json"]), src.get("map"))
                imgs_root = Path(src["images"])
                cnt = 0
                for fn, lines in per_img.items():
                    if not lines:
                        continue
                    p = resolve_image(imgs_root, fn)
                    if p is None:
                        continue
                    add_yolo_pair(p, lines, train_dir, prefix)
                    cnt += 1
                stats[prefix] = cnt
            elif typ == "voc":
                per_img = voc_or_labelme_to_yolo_rows(Path(src["annotations"]), src.get("map"), Path(src["images"]))
                imgs_root = Path(src["images"])
                cnt = 0
                for fn, lines in per_img.items():
                    if not lines:
                        continue
                    p = resolve_image(imgs_root, fn)
                    if p is None:
                        continue
                    add_yolo_pair(p, lines, train_dir, prefix)
                    cnt += 1
                stats[prefix] = cnt
            else:
                print(f"Neznamy typ {typ} — preskocen")
        except Exception as e:
            print(f"ZDROJ {prefix} ZLYHAL: {e}")

    yaml_out = {
        "path": str(out.resolve()),
        "train": "train/images",
        "val": "val/images",
        "names": {0: "Impacted", 1: "Caries", 2: "Periapical Lesion", 3: "Deep Caries"},
        "nc": 4,
    }
    (out / "data.merged.yaml").write_text(yaml.safe_dump(yaml_out, sort_keys=False), encoding="utf-8")
    print(json.dumps(stats, indent=1))
    total = sum(v for k, v in stats.items() if "val" not in k)
    print(f"TRAIN spolu: {total} | VAL(eval, nedotknuty): {nv}")
    print(f"OK -> {out}")


if __name__ == "__main__":
    main()
