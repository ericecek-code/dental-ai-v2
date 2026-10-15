"""Obrazové predspracovanie — CLAHE a ďalšie filtre."""

import cv2
import numpy as np


def apply_clahe(image_bgr: np.ndarray, clip_limit: float = 2.0, tile_grid: tuple[int, int] = (8, 8)) -> np.ndarray:
    """Aplikuje CLAHE na L kanál LAB farebného priestoru a vráti BGR obraz."""
    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid)
    l_clahe = clahe.apply(l)
    lab_clahe = cv2.merge((l_clahe, a, b))
    return cv2.cvtColor(lab_clahe, cv2.COLOR_LAB2BGR)