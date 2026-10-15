from fastapi import APIRouter

from app.core.config import settings
from app.ml.detector import CLASSES_SK

router = APIRouter()


@router.get("/health")
def health():
    from pathlib import Path

    weights_ready = Path(settings.weights_path).exists()
    return {
        "status": "healthy",
        "model_loaded": weights_ready,
        "classes": {k: v[0] for k, v in CLASSES_SK.items()},
    }
