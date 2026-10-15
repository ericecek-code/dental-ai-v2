"""Obnovenie prerušeného tréningu z last.pt:  python train_resume.py <path/to/last.pt>"""

import sys

from ultralytics import YOLO

YOLO(sys.argv[1]).train(resume=True)
