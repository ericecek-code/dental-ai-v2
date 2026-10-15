from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import analyze, health, media, results, vision
from app.core.auth import COOKIE, verify_token
from app.core.auth import router as auth_router
from app.core.config import settings

app = FastAPI(title="Dental AI v2", version="0.1.0")

_origins = [o.strip() for o in (getattr(settings, "allowed_origins", "") or "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or [],  # ALLOWED_ORIGINS env; prázdne = no origins (require explicit)
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)


@app.middleware("http")
async def password_gate(request: Request, call_next):
    path = request.url.path
    if path in ("/login", "/health", "/favicon.ico"):
        return await call_next(request)
    if request.cookies.get(COOKIE) and verify_token(request.cookies.get(COOKIE)):
        return await call_next(request)
    # prehliadaču (stránka aj assets) vráť redirect — inak po vypršaní cookie
    # stránka „zomrie" na prázdny dokument (assets idú s Accept: */*)
    accept = request.headers.get("accept", "")
    if "text/html" in accept or path.startswith("/assets/"):
        return RedirectResponse("/login")
    from fastapi.responses import JSONResponse

    return JSONResponse({"detail": "Neautorizovaný — prihláste sa."}, status_code=401)


app.include_router(health.router)
app.include_router(analyze.router)
app.include_router(results.router)
app.include_router(media.router)
app.include_router(vision.router)

# Produkčný režim (HF Spaces): servírovať build frontendu z jedného originu
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        candidate = DIST / full_path
        if full_path:
            try:
                candidate.resolve().relative_to(DIST.resolve())
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid path")
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(DIST / "index.html")
