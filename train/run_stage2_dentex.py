def main():
    import torch
    from ultralytics import YOLO
    model = YOLO(r'C:\Users\PC1\Desktop\dental-ai-v2\train\runs\merged_local5h\weights\best.pt')
    model.train(
        data=r'C:\Users\PC1\Desktop\dental-ai-v2\train\data.dentex.yaml',
        epochs=40, time=1.4, imgsz=1280, batch=4, device=0, workers=2,
        project=r'C:\Users\PC1\Desktop\dental-ai-v2\train\runs', name='stage2_dentex',
        patience=40, optimizer='AdamW', lr0=0.0002, cos_lr=True,
        flipud=0.0, fliplr=0.5, mosaic=1.0, close_mosaic=10,
    )
    m = YOLO(r'C:\Users\PC1\Desktop\dental-ai-v2\train\runs\stage2_dentex\weights\best.pt').val(
        data=r'C:\Users\PC1\Desktop\dental-ai-v2\train\data.dentex.yaml')
    print('FINAL mAP50:', m.box.map50)
    for i, c in enumerate(m.box.ap_class_index):
        print('class', int(c), 'ap50:', float(m.box.ap50[i]))

if __name__ == '__main__':
    main()
