import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from alembic.config import Config
from alembic import command

from api.auth import TokenAuthMiddleware, TOKEN_HEADER, load_or_create_token
from api.routers import admin, institution, researchers, articles, pipeline, scores, stats
from api.services.upload_utils import sweep_stale_uploads

logger = logging.getLogger(__name__)


# Local-only desktop app: callable from the Next.js dev server and an
# Electron-style packaged shell. Anything else is rejected by CORS.
# Override at deploy time via ALLOWED_ORIGINS (comma-separated).
_DEFAULT_ORIGINS = (
    "http://localhost:3000,http://127.0.0.1:3000,"
    "http://localhost:3002,http://127.0.0.1:3002,"
    "http://localhost:3012,http://127.0.0.1:3012"
)
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("ALLOWED_ORIGINS", _DEFAULT_ORIGINS).split(",")
    if o.strip()
]


@asynccontextmanager
async def lifespan(app):
    # Run Alembic migrations on startup (per D-02)
    cfg = Config()
    cfg.set_main_option(
        "script_location",
        os.path.join(os.path.dirname(__file__), "migrations"),
    )
    cfg.set_main_option(
        "sqlalchemy.url",
        os.environ.get(
            "DATABASE_URL",
            "mysql+pymysql://reciter:reciter_local@localhost:3306/reciter_desktop",
        ),
    )
    command.upgrade(cfg, "head")

    # Garbage-collect abandoned upload staging files left over from
    # previous sessions (uploads with no follow-up import).
    removed = sweep_stale_uploads()
    if removed:
        logger.info(f"Removed {removed} stale upload file(s) on startup")

    yield


app = FastAPI(title="ReCiter Desktop API", version="1.0.0", lifespan=lifespan)

# Token check runs before CORS in the response path (Starlette wraps middlewares
# inside-out), but CORS preflight OPTIONS requests are exempted in the auth
# middleware so the browser can still negotiate cross-origin headers.
_API_TOKEN = load_or_create_token()
app.add_middleware(TokenAuthMiddleware, token=_API_TOKEN)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", TOKEN_HEADER],
)

app.include_router(institution.router)
app.include_router(researchers.router)
app.include_router(articles.router)
app.include_router(pipeline.router)
app.include_router(scores.router)
app.include_router(stats.router)
app.include_router(admin.router)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
