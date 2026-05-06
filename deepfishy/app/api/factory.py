"""FastAPI application factory for DeepFishy."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from deepfishy.app.api.routes.chat import router as chat_router
from deepfishy.app.api.routes.rag import router as rag_router
from deepfishy.app.api.routes.report import router as report_router
from deepfishy.app.api.routes.response import router as response_router
from deepfishy.app.api.routes.session import router as session_router
from deepfishy.shared.logging import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    from deepfishy.infra.db.session import close_db, init_db

    logger.info("Starting DeepFishy application...")
    init_db()

    yield

    logger.info("Shutting down DeepFishy application...")
    close_db()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="DeepFishy",
        description="AI-powered financial analysis system with chat and knowledge search",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(chat_router, prefix="/api")
    app.include_router(rag_router, prefix="/api")
    app.include_router(report_router, prefix="/api")
    app.include_router(response_router, prefix="/api")
    app.include_router(session_router, prefix="/api")

    @app.get("/")
    async def root():
        return {
            "message": "DeepFishy API",
            "version": "0.1.0",
            "status": "running",
        }

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    return app
