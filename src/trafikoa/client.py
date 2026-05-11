import json
import logging
from pathlib import Path
from typing import Any

import requests

from src.config import settings

logger = logging.getLogger(__name__)


class TrafikoaAPIError(RuntimeError):
    """Raised when Trafikoa/Open Data Euskadi cannot return usable data."""


class TrafikoaClient:
    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: int = 20,
        raw_data_dir: Path | str = settings.raw_data_dir,
        save_raw: bool = settings.trafikoa_save_raw,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.raw_data_dir = Path(raw_data_dir)
        self.save_raw = save_raw
        self.session = requests.Session()

    @classmethod
    def from_env(cls) -> "TrafikoaClient":
        return cls(
            base_url=settings.trafikoa_base_url,
            api_key=settings.trafikoa_api_key,
            timeout=settings.trafikoa_timeout,
            raw_data_dir=settings.raw_data_dir,
            save_raw=settings.trafikoa_save_raw,
        )

    def build_url(self, endpoint: str) -> str:
        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            return endpoint
        return f"{self.base_url}/{endpoint.lstrip('/')}"

    def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        save_as: str | None = None,
    ) -> Any:
        headers = {"Accept": "application/json, application/geo+json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        url = self.build_url(endpoint)
        logger.info("GET Trafikoa %s params=%s", url, params or {})

        try:
            response = self.session.get(
                url,
                params=params,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.Timeout as exc:
            logger.error("Timeout calling Trafikoa endpoint %s", endpoint)
            raise TrafikoaAPIError(f"Timeout calling Trafikoa endpoint {endpoint}") from exc
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            logger.error("HTTP %s calling Trafikoa endpoint %s", status, endpoint)
            raise TrafikoaAPIError(
                f"Trafikoa endpoint {endpoint} returned HTTP {status}"
            ) from exc
        except requests.RequestException as exc:
            logger.error("Network error calling Trafikoa endpoint %s: %s", endpoint, exc)
            raise TrafikoaAPIError(
                f"Network error calling Trafikoa endpoint {endpoint}"
            ) from exc

        if response.status_code == 204 or not response.content.strip():
            logger.warning("Empty Trafikoa response for endpoint %s", endpoint)
            payload: Any = {}
        else:
            try:
                payload = response.json()
            except ValueError as exc:
                logger.error("Invalid JSON from Trafikoa endpoint %s", endpoint)
                raise TrafikoaAPIError(
                    f"Trafikoa endpoint {endpoint} did not return valid JSON"
                ) from exc

        if payload in ({}, [], None):
            logger.warning("Trafikoa endpoint %s returned no data", endpoint)

        if save_as:
            self.save_json(payload, save_as)

        return payload

    def get_paginated(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        max_pages: int | None = None,
    ) -> list[Any]:
        page = int((params or {}).get("_page", 1))
        base_params = {
            key: value for key, value in (params or {}).items() if key != "_page"
        }
        payloads = []

        while True:
            request_params = dict(base_params)
            if page > 1:
                request_params["_page"] = page

            payload = self.get(endpoint, params=request_params or None)
            payloads.append(payload)

            total_pages = _extract_total_pages(payload)
            if total_pages is None or page >= total_pages:
                break
            if max_pages is not None and len(payloads) >= max_pages:
                logger.warning(
                    "Stopping pagination for %s at max_pages=%s of totalPages=%s",
                    endpoint,
                    max_pages,
                    total_pages,
                )
                break

            page += 1

        return payloads

    def save_json(self, payload: Any, filename: str) -> Path | None:
        if not self.save_raw:
            return None

        self.raw_data_dir.mkdir(parents=True, exist_ok=True)
        path = self.raw_data_dir / filename
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("Saved raw Trafikoa response to %s", path)
        return path


def _extract_total_pages(payload: Any) -> int | None:
    if not isinstance(payload, dict):
        return None

    raw_value = payload.get("totalPages") or payload.get("total_pages")
    if raw_value is None:
        return None

    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None
