from fastapi import FastAPI

from app.api import health

app = FastAPI(title="RAG Code Reviewer")

app.include_router(health.router, prefix="/api", tags=["health"])
