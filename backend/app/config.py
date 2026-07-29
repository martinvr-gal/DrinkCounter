from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./gallery.db"
    jwt_secret: str = "development-only-change-me"
    upload_folder: Path = Path("uploads")
    tv_interval_seconds: int = 10
    admin_username: str = "admin"
    admin_password: str = "change-me"
    max_upload_bytes: int = 10 * 1024 * 1024
    cors_origins: str = "http://localhost:5173"

@lru_cache
def get_settings() -> Settings:
    return Settings()
