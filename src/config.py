from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    trafikoa_base_url: str = "https://api.euskadi.eus/traffic/v1.0"
    trafikoa_api_key: str | None = None
    trafikoa_incidents_path: str = "/incidences"
    trafikoa_cameras_path: str = "/cameras"
    backend_url: str = "http://localhost:8000"
    chroma_persist_dir: Path = Path(".chroma")
    chroma_collection_name: str = "movilidad_urbana"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
