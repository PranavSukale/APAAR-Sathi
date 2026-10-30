from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "backend/.env"), extra="ignore")

    database_owner_url: str = "postgresql+psycopg://apaar_owner:apaar_owner_pw@localhost:5544/apaar"
    database_app_url: str = "postgresql+psycopg://apaar_app:apaar_app_pw@localhost:5544/apaar"
    app_db_user: str = "apaar_app"
    app_db_password: str = "apaar_app_pw"

    key_dir: str = "backend/keys"

    jwt_secret: str = "dev-insecure-change-me"
    jwt_expire_minutes: int = 720
    login_rate_max: int = 5
    login_rate_window_seconds: int = 60

    upload_dir: str = "uploads"
    llm_enabled: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
