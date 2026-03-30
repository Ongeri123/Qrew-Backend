from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    app_name: str = "Qrew"
    app_env: str = "development"
    debug: bool = True
    secret_key: str = "change-this-in-production"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/qrew_db"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Email
    mail_username: str = ""
    mail_password: str = ""
    mail_from: str = "noreply@qrew.app"
    mail_server: str = "smtp.gmail.com"
    mail_port: int = 587

    # Rate Limiting
    max_answers_per_round: int = 1
    max_lobbies_per_player: int = 1
    lobby_cooldown_seconds: int = 300
    chat_cooldown_seconds: int = 3

    # Session
    session_expire_hours: int = 12

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()