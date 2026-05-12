import json
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic
from typing import Any

from src.config import settings
from src.rag.indexer import build_index

STATUS_FILENAME = "rag_status.json"

_refresh_lock = threading.Lock()


def get_index_status() -> dict[str, Any]:
    stored_status = _read_status()
    return _status_with_ttl(stored_status)


def refresh_index(reason: str = "manual") -> dict[str, Any]:
    with _refresh_lock:
        return _refresh_index_locked(reason=reason)


def refresh_index_if_stale() -> dict[str, Any]:
    with _refresh_lock:
        status = get_index_status()
        if not status["is_stale"]:
            status["refreshed"] = False
            return status
        return _refresh_index_locked(reason="ttl_expired")


def _refresh_index_locked(reason: str) -> dict[str, Any]:
    started_at = monotonic()
    try:
        result = build_index(reset=True)
    except Exception as exc:
        _write_error_status(exc)
        raise

    refreshed_at = _now()
    status = {
        "status": "ready",
        "refreshed": True,
        "last_refresh_reason": reason,
        "last_refresh_at": refreshed_at.isoformat(),
        "documents_indexed": result["documents_indexed"],
        "document_type_counts": result.get("document_type_counts", {}),
        "source_counts": result.get("source_counts", {}),
        "collection": result["collection"],
        "persist_dir": result["persist_dir"],
        "duration_seconds": round(monotonic() - started_at, 3),
        "last_error": None,
    }
    _write_status(status)
    return _status_with_ttl(status)


def _status_path() -> Path:
    return settings.chroma_persist_dir / STATUS_FILENAME


def _read_status() -> dict[str, Any]:
    path = _status_path()
    if not path.exists():
        return {
            "status": "missing",
            "last_refresh_at": None,
            "documents_indexed": 0,
            "document_type_counts": {},
            "source_counts": {},
            "collection": settings.chroma_collection_name,
            "persist_dir": str(settings.chroma_persist_dir),
            "last_error": None,
        }

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "status": "invalid",
            "last_refresh_at": None,
            "documents_indexed": 0,
            "document_type_counts": {},
            "source_counts": {},
            "collection": settings.chroma_collection_name,
            "persist_dir": str(settings.chroma_persist_dir),
            "last_error": str(exc),
        }


def _write_status(status: dict[str, Any]) -> None:
    path = _status_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(status, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_error_status(exc: Exception) -> None:
    status = _read_status()
    status.update(
        {
            "status": "error",
            "last_error": str(exc),
            "last_error_at": _now().isoformat(),
        }
    )
    _write_status(status)


def _status_with_ttl(status: dict[str, Any]) -> dict[str, Any]:
    ttl_seconds = settings.rag_index_ttl_seconds
    last_refresh_at = status.get("last_refresh_at")
    parsed_last_refresh = _parse_datetime(last_refresh_at)

    if parsed_last_refresh is None:
        age_seconds = None
        expires_at = None
        is_stale = True
    else:
        age_seconds = max((_now() - parsed_last_refresh).total_seconds(), 0)
        expires_at_datetime = parsed_last_refresh + timedelta(seconds=ttl_seconds)
        expires_at = expires_at_datetime.isoformat()
        is_stale = age_seconds >= ttl_seconds

    enriched_status = dict(status)
    enriched_status.update(
        {
            "ttl_seconds": ttl_seconds,
            "age_seconds": round(age_seconds, 3) if age_seconds is not None else None,
            "expires_at": expires_at,
            "is_stale": is_stale,
            "status_file": str(_status_path()),
        }
    )
    return enriched_status


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _now() -> datetime:
    return datetime.now(UTC)
