from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import institution, researchers, articles, pipeline, scores, stats

app = FastAPI(title="ReCiter Desktop API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3002"],
    allow_credentials=True,
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
