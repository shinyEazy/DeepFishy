"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api.v1.endpoints.rag import router as rag_router
from api.v1.endpoints.chat import router as chat_router
from db.session import close_db
from core.logging import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting DeepFishy application...")

    yield

    # Shutdown
    logger.info("Shutting down DeepFishy application...")
    close_db()


# Create FastAPI app
app = FastAPI(
    title="DeepFishy",
    description="AI-powered financial analysis system with chat and knowledge search",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
include_router(chat_router, prefix="/api/v1")
include_router(rag_router, prefix="/api/v1")


@get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "DeepFishy API",
        "version": "0.1.0",
        "status": "running",
    }


@get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
    }
