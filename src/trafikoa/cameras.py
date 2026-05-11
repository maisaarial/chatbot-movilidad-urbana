import csv
import math
from html import unescape
from pathlib import Path
from typing import Any

from src.config import settings
from src.trafikoa.client import TrafikoaClient

PROVINCE_BY_SOURCE = {
    "2": "Bizkaia",
    "3": "Alava-Araba",
    "4": "Gipuzkoa",
    "5": "Bizkaia",
    "6": "Alava-Araba",
    "7": "Gipuzkoa",
}

CAMERA_COLUMNS = [
    "id",
    "nombre",
    "carretera",
    "municipio",
    "provincia",
    "latitude",
    "longitude",
    "image_url",
    "source_url",
]


def get_cameras(client: TrafikoaClient | None = None) -> list[dict[str, Any]]:
    client = client or TrafikoaClient.from_env()
    endpoint = settings.trafikoa_cameras_path

    payloads = client.get_paginated(endpoint)
    raw_payload = {
        "endpoint": client.build_url(endpoint),
        "pages": payloads,
    }
    client.save_json(raw_payload, "cameras_raw.json")

    cameras = []
    for payload in payloads:
        cameras.extend(_normalise_items(payload))

    source_url = client.build_url(endpoint)
    rows = [_normalise_camera(item, source_url) for item in cameras]
    _save_csv(rows, settings.processed_data_dir / "cameras.csv", CAMERA_COLUMNS)
    return rows


def download_cameras(client: TrafikoaClient | None = None) -> list[dict[str, Any]]:
    return get_cameras(client)


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


def _normalise_camera(item: dict[str, Any], source_url: str) -> dict[str, Any]:
    source_id = _clean_text(item.get("sourceId"))
    latitude, longitude = _normalise_coordinates(
        item.get("latitude"),
        item.get("longitude"),
    )

    return {
        "id": _clean_text(item.get("cameraId") or item.get("id")),
        "nombre": _clean_text(item.get("cameraName") or item.get("name")),
        "carretera": _clean_text(item.get("road")),
        "municipio": _clean_text(item.get("cityTown") or item.get("address")),
        "provincia": _clean_text(item.get("province"))
        or PROVINCE_BY_SOURCE.get(source_id, ""),
        "latitude": latitude,
        "longitude": longitude,
        "image_url": _clean_text(item.get("urlImage") or item.get("imageUrl")),
        "source_url": source_url,
    }


def _save_csv(rows: list[dict[str, Any]], path: Path, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _normalise_coordinates(
    latitude: Any,
    longitude: Any,
) -> tuple[float | None, float | None]:
    lat = _to_float(latitude)
    lon = _to_float(longitude)
    if lat is None or lon is None:
        return lat, lon

    if abs(lat) <= 90 and abs(lon) <= 180:
        return lat, lon

    if abs(lat) > 1000 and abs(lon) > 1000:
        return _utm_zone_30n_to_wgs84(easting=lon, northing=lat)

    return lat, lon


def _utm_zone_30n_to_wgs84(easting: float, northing: float) -> tuple[float, float]:
    # Some Trafikoa camera sources expose ETRS89/UTM zone 30N coordinates.
    axis = 6378137.0
    eccentricity_sq = 0.0066943799901413165
    eccentricity_prime_sq = eccentricity_sq / (1 - eccentricity_sq)
    scale = 0.9996

    x = easting - 500000.0
    y = northing
    zone_origin = math.radians(-3.0)

    meridional_arc = y / scale
    mu = meridional_arc / (
        axis
        * (
            1
            - eccentricity_sq / 4
            - 3 * eccentricity_sq**2 / 64
            - 5 * eccentricity_sq**3 / 256
        )
    )

    e1 = (1 - math.sqrt(1 - eccentricity_sq)) / (1 + math.sqrt(1 - eccentricity_sq))
    footpoint_lat = (
        mu
        + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
        + (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
        + (151 * e1**3 / 96) * math.sin(6 * mu)
        + (1097 * e1**4 / 512) * math.sin(8 * mu)
    )

    sin_fp = math.sin(footpoint_lat)
    cos_fp = math.cos(footpoint_lat)
    tan_fp = math.tan(footpoint_lat)

    radius_n = axis / math.sqrt(1 - eccentricity_sq * sin_fp**2)
    radius_r = (
        axis
        * (1 - eccentricity_sq)
        / (1 - eccentricity_sq * sin_fp**2) ** 1.5
    )
    t1 = tan_fp**2
    c1 = eccentricity_prime_sq * cos_fp**2
    d = x / (radius_n * scale)

    lat_rad = footpoint_lat - (
        radius_n
        * tan_fp
        / radius_r
        * (
            d**2 / 2
            - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * eccentricity_prime_sq)
            * d**4
            / 24
            + (
                61
                + 90 * t1
                + 298 * c1
                + 45 * t1**2
                - 252 * eccentricity_prime_sq
                - 3 * c1**2
            )
            * d**6
            / 720
        )
    )
    lon_rad = zone_origin + (
        d
        - (1 + 2 * t1 + c1) * d**3 / 6
        + (
            5
            - 2 * c1
            + 28 * t1
            - 3 * c1**2
            + 8 * eccentricity_prime_sq
            + 24 * t1**2
        )
        * d**5
        / 120
    ) / cos_fp

    return round(math.degrees(lat_rad), 8), round(math.degrees(lon_rad), 8)


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return unescape(str(value)).strip()


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
