from fastapi import FastAPI

from app.api import health, index, projects
from app.db.session import Base, engine
from app.models import chunk, document, project  # noqa: F401

Base.metadata.create_all(bind=engine)

app = FastAPI(title="RAG Code Reviewer")

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(projects.router, prefix="/api", tags=["projects"])
app.include_router(index.router, prefix="/api", tags=["index"])
