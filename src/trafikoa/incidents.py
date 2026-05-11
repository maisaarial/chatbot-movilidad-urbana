import csv
from datetime import date
from html import unescape
from pathlib import Path
from typing import Any

from src.config import settings
from src.trafikoa.client import TrafikoaClient

SOURCE_NAMES = {
    "1": "Gobierno Pais Vasco",
    "2": "Diputacion Foral de Bizkaia",
    "3": "Diputacion Foral de Alava",
    "4": "Diputacion Foral de Gipuzkoa",
    "5": "Ayuntamiento Bilbao",
    "6": "Ayuntamiento Vitoria-Gasteiz",
    "7": "Ayuntamiento de Donostia-San Sebastian",
}

INCIDENT_COLUMNS = [
    "id",
    "timestamp",
    "tipo",
    "carretera",
    "causa",
    "sentido",
    "municipio",
    "provincia",
    "fuente",
    "latitude",
    "longitude",
]


def get_current_incidents(
    client: TrafikoaClient | None = None,
    target_date: date | None = None,
) -> list[dict[str, Any]]:
    client = client or TrafikoaClient.from_env()
    target_date = target_date or date.today()
    endpoint = _build_current_incidents_endpoint(target_date)

    payloads = client.get_paginated(endpoint)
    raw_payload = {
        "endpoint": client.build_url(endpoint),
        "date": target_date.isoformat(),
        "pages": payloads,
    }
    client.save_json(raw_payload, "incidents_raw.json")

    incidents = []
    for payload in payloads:
        incidents.extend(_normalise_items(payload))

    rows = [_normalise_incident(item) for item in incidents]
    _save_csv(rows, settings.processed_data_dir / "incidents.csv", INCIDENT_COLUMNS)
    return rows


def _build_current_incidents_endpoint(target_date: date) -> str:
    template = settings.trafikoa_incidents_path
    if "{year}" in template or "{month}" in template or "{day}" in template:
        return template.format(
            year=target_date.year,
            month=target_date.month,
            day=target_date.day,
        )

    base_endpoint = template.rstrip("/")
    if base_endpoint.endswith("/incidences"):
        return (
            f"{base_endpoint}/byDate/"
            f"{target_date.year}/{target_date.month}/{target_date.day}"
        )

    return template


def download_incidents(client: TrafikoaClient | None = None) -> list[dict[str, Any]]:
    return get_current_incidents(client)


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


def _normalise_incident(item: dict[str, Any]) -> dict[str, Any]:
    source_id = _clean_text(item.get("sourceId"))
    return {
        "id": _clean_text(item.get("incidenceId")),
        "timestamp": _clean_text(item.get("startDate") or item.get("timestamp")),
        "tipo": _clean_text(item.get("incidenceType") or item.get("type")),
        "carretera": _clean_text(item.get("road") or item.get("roadName")),
        "causa": _clean_text(item.get("cause")),
        "sentido": _clean_text(item.get("direction")),
        "municipio": _clean_text(item.get("cityTown") or item.get("municipality")),
        "provincia": _clean_text(item.get("province")),
        "fuente": SOURCE_NAMES.get(source_id, source_id),
        "latitude": _to_float(item.get("latitude")),
        "longitude": _to_float(item.get("longitude")),
    }


def _save_csv(rows: list[dict[str, Any]], path: Path, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return unescape(str(value)).strip()


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
