import torch
from ultralytics import YOLO

def main():
    model = YOLO(r'C:\Users\PC1\Desktop\dental-ai-v2\backend\weights\best.pt')
    model.train(
        data=r'C:\Users\PC1\Desktop\dental-ai-v2\train\runs\merged\data.merged.yaml',
        epochs=200, time=5.5, imgsz=1280, batch=4, device=0, workers=4,
        project=r'C:\Users\PC1\Desktop\dental-ai-v2\train\runs', name='merged_local5h',
        patience=30, optimizer='AdamW', lr0=0.0003, cos_lr=True,
        flipud=0.0, fliplr=0.5, mosaic=1.0, close_mosaic=10,
    )
    m = YOLO(r'C:\Users\PC1\Desktop\dental-ai-v2\train\runs\merged_local5h\weights\best.pt').val(
        data=r'C:\Users\PC1\Desktop\dental-ai-v2\train\runs\merged\data.merged.yaml')
    print('FINAL mAP50:', m.box.map50)

if __name__ == '__main__':
    main()
