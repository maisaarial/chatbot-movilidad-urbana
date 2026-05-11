from typing import Any

from src.config import settings
from src.trafikoa.client import TrafikoaClient


def download_incidents(client: TrafikoaClient | None = None) -> list[dict[str, Any]]:
    client = client or TrafikoaClient.from_env()
    payloads = client.get_paginated(settings.trafikoa_incidents_path)

    incidents = []
    for payload in payloads:
        incidents.extend(_normalise_items(payload))
    return incidents


def _normalise_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("incidences", "incidents", "items", "features", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        if "totalPages" in payload or "total_pages" in payload:
            return []
        return [payload]
    return []
