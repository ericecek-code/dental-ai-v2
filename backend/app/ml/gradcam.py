"""Grad-CAM heatmapa pre YOLO model — „kam sa AI pozerá".

Port zo starého projektu (dental-ai) s úpravami: 1280 px vstup (zhoda s tréningom),
cieľ = kanál triedy v hlavike, fallback na priemerný kanál tried.
"""

import cv2
import numpy as np
import torch

from app.ml.detector import load_model


def _last_conv_layer(net: torch.nn.Module) -> torch.nn.Module | None:
    last = None
    for m in net.modules():
        if isinstance(m, torch.nn.Conv2d):
            last = m
    return last


def generate_gradcam(image_path: str, class_id: int | None = None,
                     imgsz: int = 1280, alpha: float = 0.45) -> np.ndarray:
    """Vráti BGR overlay originálnej snímky s Grad-CAM heatmapou."""
    yolo = load_model()
    net = yolo.model
    net.eval()

    last_conv = _last_conv_layer(net)
    if last_conv is None:
        raise RuntimeError("Model nemá Conv vrstvu pre Grad-CAM.")

    acts: list[np.ndarray] = []
    grads: list[np.ndarray] = []

    def fwd(_m, _i, output):
        acts.append(output.detach())

    def bwd(_m, _gi, grad_output):
        grads.append(grad_output[0].detach())

    h1 = last_conv.register_forward_hook(fwd)
    h2 = last_conv.register_full_backward_hook(bwd)
    try:
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Nepodarilo sa načítať {image_path}")
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (imgsz, imgsz))
        tensor = torch.from_numpy(resized).permute(2, 0, 1).float().unsqueeze(0) / 255.0
        tensor = tensor.to(next(net.parameters()).device)

        with torch.enable_grad():
            tensor.requires_grad_(True)
            out = net(tensor)
            if isinstance(out, (list, tuple)):
                out = out[0]
            # YOLOv8 head výstup: (1, 4+nc, N) — kanály tried od indexu 4
            if out.dim() == 3 and out.shape[1] >= 5:
                if class_id is None:
                    cls_map = out[0, 4:]
                    target = cls_map[cls_map.sum(dim=1).argmax()].sum()
                else:
                    target = out[0, 4 + class_id].sum()
            else:
                target = out.sum()
            net.zero_grad()
            target.backward()

        if not acts or not grads:
            raise RuntimeError("Hooky nevrátili aktivácie/gradienty.")
        act = acts[0].detach().cpu().numpy()
        grad = grads[0].detach().cpu().numpy()
        weights = grad.mean(axis=(2, 3), keepdims=True)
        cam = np.maximum(weights * act, 0)  # ReLU
        cam = cam.sum(axis=1, keepdims=True)
        cam = cam.squeeze()
        cam -= cam.min()
        if cam.max() > 0:
            cam /= cam.max()
    finally:
        h1.remove()
        h2.remove()
        net.zero_grad(set_to_none=True)

    cam_img = cv2.resize(cam, (img.shape[1], img.shape[0]))
    heat = cv2.applyColorMap(np.uint8(255 * cam_img), cv2.COLORMAP_JET)
    return cv2.addWeighted(img, 1 - alpha, heat, alpha, 0)
