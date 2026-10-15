"""Poriadne prihlásenie pre deploy — používatelia v .env (USERS="meno:heslo,meno2:heslo2").

Fallback: APP_PASSWORD (jedno spoločné heslo, demo režim).
Session: podpísaná cookie (HMAC z tajomstva), 12 h platnosť — žiadna DB potrebná.
"""

import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.config import settings

router = APIRouter()
COOKIE = "dental_session"
SESSION_HOURS = 12

# tajomstvo: z .env (SECRET) alebo odvodené z hesla (demo stačí)
_SECRET_FILE = Path("data/.secret")


def _secret() -> bytes:
    s = getattr(settings, "secret", "")
    if s:
        return s.encode()
    _SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    if _SECRET_FILE.exists():
        return _SECRET_FILE.read_bytes()
    tok = secrets.token_hex(32).encode()
    _SECRET_FILE.write_bytes(tok)
    return tok


def _users() -> dict[str, str]:
    users = {}
    raw = getattr(settings, "users", "") or ""
    for pair in raw.split(","):
        if ":" in pair:
            name, pw = pair.split(":", 1)
            users[name.strip()] = pw
    if not users and settings.app_password:
        # demo režim: obe varianty mena (s aj bez diakritiky)
        users["lekár"] = settings.app_password
        users["lekar"] = settings.app_password
    return users


def _sign(payload: str) -> str:
    return hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()[:32]


def make_token(username: str) -> str:
    payload = json.dumps({"u": username, "exp": time.time() + SESSION_HOURS * 3600})
    import base64

    b = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    return f"{b}.{_sign(b)}"


def verify_token(token: str | None) -> str | None:
    if not token or "." not in token:
        return None
    b, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(sig, _sign(b)):
        return None
    import base64

    try:
        payload = json.loads(base64.urlsafe_b64decode(b + "=" * (-len(b) % 4)))
    except Exception:
        return None
    if payload.get("exp", 0) < time.time():
        return None
    return payload.get("u")


LOGIN_HTML = """<!doctype html><html lang="sk"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dental AI — prihlásenie</title><style>
body{margin:0;font-family:system-ui;background:radial-gradient(1200px 600px at 70% -10%,#0f766e33,#020617);color:#e2e8f0;display:flex;align-items:center;justify-content:center;min-height:100vh}
.box{background:rgba(15,23,42,.85);backdrop-filter:blur(14px);border:1px solid #1e293b;border-radius:20px;padding:36px;width:min(360px,90vw);text-align:center;box-shadow:0 20px 60px #0009}
.logo{width:64px;height:64px;border-radius:50%;background:linear-gradient(135deg,#14b8a6,#0284c7);display:flex;align-items:center;justify-content:center;font-size:32px;margin:0 auto 14px}
h1{font-size:20px;margin:0 0 4px}p{color:#94a3b8;font-size:13px;margin:0 0 22px}
input{width:100%;box-sizing:border-box;padding:12px;border-radius:12px;border:1px solid #334155;background:#020617;color:#e2e8f0;margin-bottom:12px;font-size:14px}
input:focus{outline:none;border-color:#14b8a6;box-shadow:0 0 0 3px #14b8a633}
button{width:100%;padding:12px;border:0;border-radius:12px;background:linear-gradient(90deg,#14b8a6,#0284c7);color:#04121a;font-weight:700;font-size:14px;cursor:pointer;transition:transform .15s}
button:hover{transform:translateY(-1px)}
.err{color:#f87171;font-size:12px;margin-bottom:10px}
.hint{color:#475569;font-size:11px;margin-top:16px}
</style></head><body><div class="box">
<div class="logo">🦷</div><h1>Dental AI</h1>
<p>Súkromné demo — prihláste sa</p>
{error}
<form method="post" action="/login">
<input name="username" placeholder="meno" autofocus autocomplete="username">
<input type="password" name="password" placeholder="heslo" autocomplete="current-password">
<button>Prihlásiť sa</button></form>
<p class="hint">Prístup má len pozvaný personál.</p></div></body></html>"""


@router.get("/login", include_in_schema=False)
def login_page(error: str = ""):
    err = '<p class="err">Nesprávne meno alebo heslo.</p>' if error else ""
    return HTMLResponse(LOGIN_HTML.replace("{error}", err))


@router.post("/login", include_in_schema=False)
def login(request: Request, username: str = Form(""), password: str = Form("")):
    users = _users()
    if username in users and hmac.compare_digest(
        password.encode("utf-8"), users[username].encode("utf-8")
    ):
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie(COOKIE, make_token(username), httponly=True, samesite="lax",
                        secure=getattr(settings, "cookie_secure", False),
                        max_age=SESSION_HOURS * 3600)
        return resp
    return RedirectResponse("/login?error=1", status_code=303)


@router.get("/logout", include_in_schema=False)
def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(COOKIE)
    return resp
