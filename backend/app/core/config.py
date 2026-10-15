from pathlib import Path

from pydantic_settings import BaseSettings
from pydantic import model_validator


class Settings(BaseSettings):
    app_password: str = ""            # Must be set explicitly; empty raises error at startup
    users: str = ""            # USERS="lekár:heslo1,asistentka:heslo2" (vyhradí app_password)
    secret: str = ""           # podpis session cookies; prázdne → auto-generované data/.secret
    conf_threshold: float = 0.25
    max_upload_mb: int = 15
    weights_path: str = "weights/best.pt"
    # Test-Time Augmentation
    tta_enabled: bool = True
    tta_augmentations: int = 5
    # MC Dropout uncertainty
    mc_dropout_enabled: bool = True
    mc_dropout_passes: int = 5
    mc_dropout_rate: float = 0.1
    # Supabase (prázdne => lokálny SQLite fallback)
    supabase_url: str = ""
    supabase_anon_key: str = ""
    # Webová vrstva
    gemini_api_key: str = ""    # GEMINI_API_KEY — AI druhý názor (VLM)
    gemini_model: str = "gemini-2.5-flash-lite"            # GEMINI_MODEL — konkrétny model
    gemini_fallback_models: str = "gemini-2.5-flash-lite"  # GEMINI_FALLBACK_MODELS — záložné modely (čiarkou)
    allowed_origins: str = ""   # ALLOWED_ORIGINS="https://x,https://y" (prázdne = demo wildcard)
    cookie_secure: bool = False # secure cookie (True pri HTTPS deploye)



    model_config = {"env_file": str(Path(__file__).resolve().parents[3] / ".env"), "extra": "ignore"}

    @model_validator(mode="after")
    def _check_app_password(self) -> "Settings":
        if self.app_password == "":
            raise ValueError("APP_PASSWORD must be set explicitly; empty password is not allowed for security.")
        return self

settings = Settings()
