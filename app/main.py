from fastapi import FastAPI

from app.api import health, index, projects, reviews
from app.core.logging import configure_logging
from app.core.middleware import RequestIDMiddleware
from app.db.session import Base, engine
from app.models import chunk, document, project, request_log, review  # noqa: F401

configure_logging()
Base.metadata.create_all(bind=engine)

app = FastAPI(title="RAG Code Reviewer")

app.add_middleware(RequestIDMiddleware)

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(projects.router, prefix="/api", tags=["projects"])
app.include_router(index.router, prefix="/api", tags=["index"])
app.include_router(reviews.router, prefix="/api", tags=["reviews"])
