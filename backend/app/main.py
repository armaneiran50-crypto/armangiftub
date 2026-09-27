from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from .api import auth, lanes, misc, portal, providers, rfqs, whatsapp
from .config import get_settings
from .db import SessionLocal, engine
from .models import Role, User
from .security import hash_password


def check_settings() -> None:
    s = get_settings()
    if s.env == "production":
        if s.jwt_secret == "change-me-in-production" or len(s.jwt_secret) < 32:
            raise RuntimeError("LOGIRAD_JWT_SECRET must be set to a random value of at least 32 characters")
        if s.admin_password == "change-me":
            raise RuntimeError("LOGIRAD_ADMIN_PASSWORD must be changed in production")


def run_migrations() -> None:
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    root = Path(__file__).resolve().parent.parent
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "migrations"))
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")


def init_db() -> None:
    run_migrations()
    s = get_settings()
    with SessionLocal() as db:
        if not db.scalar(select(User.id).limit(1)):
            db.add(User(email=s.admin_email.lower(), password_hash=hash_password(s.admin_password), role=Role.admin))
            db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    check_settings()
    init_db()
    yield


app = FastAPI(title="Logirad API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in get_settings().cors_origins.split(",")],
                   allow_methods=["*"], allow_headers=["*"])
for r in (auth.router, rfqs.router, rfqs.bookings_router, providers.router, portal.router, whatsapp.router,
          lanes.router, misc.router):
    app.include_router(r)


@app.get("/api/config")
def public_config():
    """Public settings the website needs at runtime."""
    s = get_settings()
    return {"whatsapp_number": s.whatsapp_display_number or None, "ai_intake": s.ai_enabled}


@app.get("/api/health")
def health():
    return {"ok": True}
