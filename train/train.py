"""Tréning YOLO na DENTEX — GTX 1080 Ti (Pascal: FP32, amp=False).

Použitie:
  python train.py --smoke                    # sanity: v8n, 640, 2 epóchy (~5 min)
  python train.py                            # hlavný run: v8s, 1280, 100 epóch (~8 h)
  python train.py --model yolov8m.pt --batch 3 --epochs 100
"""

import argparse
from pathlib import Path

from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="yolov8s.pt")
    p.add_argument("--imgsz", type=int, default=1280)
    p.add_argument("--epochs", type=int, default=40,
                   help="nutné minimum: early stopping (patience) skončí skôr, keď mAP prestane rásť")
    p.add_argument("--batch", type=int, default=4)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--patience", type=int, default=12,
                   help="early stopping: po N epóch bez zlepšenia skonči")
    p.add_argument("--data", default=str(ROOT / "data.dentex.yaml"))
    p.add_argument("--name", default=None)
    p.add_argument("--smoke", action="store_true", help="rýchly sanity test pipeline")
    args = p.parse_args()

    if args.smoke:
        args.model, args.imgsz, args.epochs = "yolov8n.pt", 640, 2

    name = args.name or f"{Path(args.model).stem}_dentex_{args.imgsz}"
    print(f"=== Tréning: {args.model} imgsz={args.imgsz} epochs={args.epochs} batch={args.batch} ===")

    model = YOLO(args.model)  # pretrained COCO váhy (auto-download)
    model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=0,
        amp=False,          # Pascal nemá tensor cores — FP16 by bol pomalší
        workers=args.workers,
        cache="disk",
        patience=args.patience,  # stop, keď N epóch žiadne zlepšenie — žiadne zbytočné epochy
        seed=42,
        project=str(ROOT / "runs"),
        name=name,
        plots=True,
    )

    metrics = model.val(data=args.data, imgsz=args.imgsz, device=0)
    print("=== Validácia (val split) ===")
    print(f"mAP50: {metrics.box.map50:.3f} | mAP50-95: {metrics.box.map:.3f}")

    best = Path(model.trainer.save_dir) / "weights" / "best.pt"
    print(f"Najlepšie váhy: {best}")


if __name__ == "__main__":
    main()
