from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    trafikoa_base_url: str = "https://api.euskadi.eus/traffic/v1.0"
    trafikoa_api_key: str | None = None
    trafikoa_incidents_path: str = "/incidences/byDate/{year}/{month}/{day}"
    trafikoa_cameras_path: str = "/cameras"
    trafikoa_flows_path: str = "/flows/byDate/{year}/{month}/{day}"
    trafikoa_meters_path: str = "/meters"
    trafikoa_level_of_service_path: str = "/levelOfService"
    trafikoa_congestion_source_id: int = 5
    trafikoa_congestion_max_flow_pages: int = 25
    congestion_low_threshold: float = 50
    congestion_high_threshold: float = 150
    trafikoa_timeout: int = 20
    trafikoa_save_raw: bool = True
    raw_data_dir: Path = Path("data/raw")
    processed_data_dir: Path = Path("data/processed")
    backend_url: str = "http://localhost:8000"
    chroma_persist_dir: Path = Path("data/vectorstore")
    chroma_collection_name: str = "movilidad_urbana"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    ollama_timeout: int = 180
    rag_top_k: int = 5
    rag_index_ttl_seconds: int = 300

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
