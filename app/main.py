from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.database import init_db , close_db
from app.redis import init_redis, close_redis

# Routers 
from app.routers import venue as venue_router
from app.routers import player as player_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs on startup and shutdown.
    Initializes database and Redis connections.
    """
    print(f" Starting {settings.app_name}...")

    # Startup
    print(f"starting {settings.app_name}...")
    await init_db()
    await init_redis()
    print(f"{settings.app_name} is ready!" )

    yield  # App runs here

    # Shutdown
    print(f"Shutting down {settings.app_name}...")
    await close_redis()
    await close_db()
    print(" Goodbye")


app = FastAPI(
    title="Qrew API",
    description="Real time social gaming platform for venues",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.app_env == "development" else None,
    redoc_url=None,
)


# CORS — allows browser to talk to API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_env == "development" else [settings.app_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(venue_router.router)
app.include_router(player_router.router)

# Health check — Railway and Render use this to verify app is running
@app.get("/health")
async def health_check():
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
        "play": "/play/{venue_slug}",
    }