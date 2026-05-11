import csv
import re
import unicodedata
from pathlib import Path
from typing import Any

from src.config import settings

CAMERA_SEARCH_FIELDS = ["nombre", "carretera", "municipio", "provincia"]
ROAD_PATTERN = re.compile(r"\b(?:a|ap|bi|gi|n)-\s*\d+[a-z]?\b", re.IGNORECASE)


def search_cameras(
    q: str | None = None,
    municipio: str | None = None,
    carretera: str | None = None,
    provincia: str | None = None,
    limit: int = 10,
    only_with_image: bool = False,
) -> list[dict[str, Any]]:
    cameras = _load_cameras(settings.processed_data_dir / "cameras.csv")
    limit = max(1, min(limit, 100))

    scored_results = []
    for row_number, camera in enumerate(cameras):
        if only_with_image and not _has_image(camera):
            continue
        score = _score_camera(
            camera=camera,
            q=q,
            municipio=municipio,
            carretera=carretera,
            provincia=provincia,
        )
        if score is None:
            continue
        scored_results.append((score, row_number, camera_to_response(camera)))

    scored_results.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in scored_results[:limit]]


def normalize_text(text: Any) -> str:
    if text is None:
        return ""
    normalized = unicodedata.normalize("NFKD", str(text).lower())
    without_accents = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    without_punctuation = re.sub(r"[^\w\s-]", " ", without_accents)
    compact = re.sub(r"\s+", " ", without_punctuation).strip()
    return re.sub(r"\s*-\s*", "-", compact)


def camera_to_response(camera: dict[str, Any]) -> dict[str, Any]:
    latitude = _to_float(camera.get("latitude"))
    longitude = _to_float(camera.get("longitude"))
    maps_url = _maps_url(latitude, longitude)

    return {
        "id": _clean(camera.get("id")),
        "nombre": _clean(camera.get("nombre")),
        "carretera": _clean(camera.get("carretera")),
        "municipio": _clean(camera.get("municipio")),
        "provincia": _clean(camera.get("provincia")),
        "latitude": latitude,
        "longitude": longitude,
        "source_id": _clean(camera.get("source_id")),
        "kilometer": _clean(camera.get("kilometer")),
        "raw_latitude": _clean(camera.get("raw_latitude")),
        "raw_longitude": _clean(camera.get("raw_longitude")),
        "image_url": _clean(camera.get("image_url")),
        "stream_url": _clean(camera.get("stream_url")),
        "source_url": _clean(camera.get("source_url")),
        "maps_url": maps_url,
    }


def get_camera_by_id(camera_id: str) -> dict[str, Any] | None:
    normalized_camera_id = normalize_text(camera_id)
    if not normalized_camera_id:
        return None

    for camera in _load_cameras(settings.processed_data_dir / "cameras.csv"):
        if normalize_text(camera.get("id")) == normalized_camera_id:
            return camera_to_response(camera)
    return None


def _load_cameras(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8", newline="") as csv_file:
        return [row for row in csv.DictReader(csv_file)]


def _score_camera(
    camera: dict[str, Any],
    q: str | None,
    municipio: str | None,
    carretera: str | None,
    provincia: str | None,
) -> int | None:
    score = 0

    carretera_score = _field_match_score(
        query=carretera,
        value=camera.get("carretera"),
        exact_score=1000,
        contains_score=650,
        road=True,
    )
    if carretera_score is None:
        return None
    score += carretera_score

    municipio_score = _field_match_score(
        query=municipio,
        value=camera.get("municipio"),
        exact_score=900,
        contains_score=550,
    )
    if municipio_score is None:
        return None
    score += municipio_score

    provincia_score = _field_match_score(
        query=provincia,
        value=camera.get("provincia"),
        exact_score=700,
        contains_score=450,
    )
    if provincia_score is None:
        return None
    score += provincia_score

    q_score = _query_match_score(camera, q)
    if q_score is None:
        return None
    score += q_score
    score += _availability_score(camera)

    return score


def _availability_score(camera: dict[str, Any]) -> int:
    score = 0
    if _has_image(camera):
        score += 120
    if _has_coordinates(camera):
        score += 40
    return score


def _field_match_score(
    query: str | None,
    value: Any,
    exact_score: int,
    contains_score: int,
    road: bool = False,
) -> int | None:
    if not query:
        return 0

    normalized_query = _normalize_road(query) if road else normalize_text(query)
    normalized_value = _normalize_road(value) if road else normalize_text(value)
    if not normalized_query:
        return 0
    if not normalized_value:
        return None

    if normalized_query == normalized_value:
        return exact_score
    if normalized_query in normalized_value or normalized_value in normalized_query:
        return contains_score
    return None


def _query_match_score(camera: dict[str, Any], q: str | None) -> int | None:
    if not q:
        return 0

    q_normalized = normalize_text(q)
    if not q_normalized:
        return 0

    q_road = _extract_road(q_normalized)
    if q_road and q_road == _normalize_road(camera.get("carretera")):
        return 800

    field_values = {
        field: normalize_text(camera.get(field))
        for field in CAMERA_SEARCH_FIELDS
    }

    if q_normalized == field_values["municipio"]:
        return 750
    if q_normalized == field_values["provincia"]:
        return 650
    if q_normalized == field_values["carretera"]:
        return 800
    if q_normalized == field_values["nombre"]:
        return 500

    haystack = " ".join(field_values.values())
    if q_normalized in haystack:
        return 300

    tokens = [token for token in q_normalized.split() if len(token) > 2]
    if tokens and all(token in haystack for token in tokens):
        return 200

    return None


def _normalize_road(value: Any) -> str:
    return normalize_text(value).replace(" ", "")


def _extract_road(value: str) -> str | None:
    match = ROAD_PATTERN.search(value)
    if not match:
        return None
    return _normalize_road(match.group(0))


def _maps_url(latitude: float | None, longitude: float | None) -> str:
    if latitude is None or longitude is None:
        return ""
    return f"https://www.google.com/maps?q={latitude},{longitude}"


def _has_image(camera: dict[str, Any]) -> bool:
    return bool(_clean(camera.get("image_url")))


def _has_coordinates(camera: dict[str, Any]) -> bool:
    return (
        _to_float(camera.get("latitude")) is not None
        and _to_float(camera.get("longitude")) is not None
    )


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
