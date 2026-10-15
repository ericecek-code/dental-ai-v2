"""Validácia hotových váh na val splite:  python val_best.py <path/to/best.pt>"""

import sys
from pathlib import Path

from ultralytics import YOLO


def main() -> None:
    m = YOLO(sys.argv[1])
    r = m.val(data=str(Path(__file__).parent / "data.dentex.yaml"),
              imgsz=1280, device=0, workers=0)
    print(f"SUMMARY mAP50={r.box.map50:.4f} mAP50-95={r.box.map:.4f} P={r.box.mp:.4f} R={r.box.mr:.4f}")


if __name__ == "__main__":
    main()
