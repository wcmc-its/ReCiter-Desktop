import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from alembic.config import Config
from alembic import command

from api.routers import institution, researchers, articles, pipeline, scores, stats


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
    yield


app = FastAPI(title="ReCiter Desktop API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(institution.router)
app.include_router(researchers.router)
app.include_router(articles.router)
app.include_router(pipeline.router)
app.include_router(scores.router)
app.include_router(stats.router)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
