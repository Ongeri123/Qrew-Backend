from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.database import init_db
from app.redis import init_redis, close_redis

# Routers — will be added as we build each phase
# from app.routers import venue, player, game


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs on startup and shutdown.
    Initializes database and Redis connections.
    """
    print(f" Starting {settings.app_name}...")

    # Startup
    await init_db()
    print(" Database connected")

    await init_redis()
    print(" Redis connected")

    yield  # App runs here

    # Shutdown
    await close_redis()
    print(" Qrew shutting down")


app = FastAPI(
    title="Qrew API",
    description="Real time social gaming platform for venues",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,   # hide docs in production
    redoc_url="/redoc" if settings.debug else None,
)


# CORS — allows browser to talk to API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else ["https://qrew.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check — Railway and Render use this to verify app is running
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "app": settings.app_name,
        "env": settings.app_env,
    }


# Root
@app.get("/")
async def root():
    return {
        "message": "Welcome to Qrew API",
        "docs": "/docs",
    }