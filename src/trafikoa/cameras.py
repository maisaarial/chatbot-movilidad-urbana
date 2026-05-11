from typing import Any

from src.config import settings
from src.trafikoa.client import TrafikoaClient


def download_cameras(client: TrafikoaClient | None = None) -> list[dict[str, Any]]:
    client = client or TrafikoaClient.from_env()
    payloads = client.get_paginated(settings.trafikoa_cameras_path)

    cameras = []
    for payload in payloads:
        cameras.extend(_normalise_items(payload))
    return cameras


def _normalise_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("cameras", "items", "features", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if "totalPages" in payload or "total_pages" in payload:
            return []
        return [payload]
    return []
