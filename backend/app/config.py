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
    counter_database_path: Path = Path("counter-data/counter.db")
    clips_folder: Path = Path("clips")
    max_clip_bytes: int = 1024 * 1024 * 1024
    ads_folder: Path = Path("anuncios")
    max_ad_bytes: int = 10 * 1024 * 1024
    spotify_client_id: str | None = None
    spotify_client_secret: str | None = None
    spotify_redirect_uri: str = "http://localhost:8000/admin/spotify/callback"
    spotify_default_playlist: str | None = None
    spotify_refresh_token: str | None = None
    spotify_autoplay: bool = True
    spotify_token_path: Path = Path("counter-data/spotify-token.json")

@lru_cache
def get_settings() -> Settings:
    return Settings()
