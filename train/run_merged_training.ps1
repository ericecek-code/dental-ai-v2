# Lokalny trening na merged datasete — cap 13 h (user limit 14 h).
# Spustenie: powershell -File run_merged_training.ps1
$ErrorActionPreference = 'Continue'
$v2 = 'C:\Users\PC1\Desktop\dental-ai-v2'
$py = "$v2\backend\.venv\Scripts\python.exe"
Set-Location "$v2\backend"

$py -c @"
import torch
from ultralytics import YOLO
model = YOLO('weights/best.pt')  # fine-tune z aktualneho best (72,3 % Caries recall zaklad)
model.train(
    data=r'C:\Users\PC1\Desktop\dental-ai-v2\train\runs\merged\data.merged.yaml',
    epochs=120,              # pojistka — zastavi skor `time`
    time=13,                 # HARD CAP hodiny (ultralytics native)
    imgsz=1280, batch=6,
    device=0, workers=4,
    project=r'C:\Users\PC1\Desktop\dental-ai-v2\train\runs', name='merged_v1',
    patience=20, optimizer='AdamW', lr0=0.0005, cos_lr=True,
    flipud=0.0, fliplr=0.5, mosaic=1.0, close_mosaic=10,
    patience=20, optimizer='AdamW', lr0=0.0003, cos_lr=True,
metrics = YOLO(r'C:\Users\PC1\Desktop\dental-ai-v2\train\runs\merged_v1\weights\best.pt').val(
    data=r'C:\Users\PC1\Desktop\dental-ai-v2\train\runs\merged\data.merged.yaml')
print('FINAL mAP50:', metrics.box.map50)
"@
