from typing import Any

import requests

from src.config import settings


class TrafikoaClient:
    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: int = 20,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    @classmethod
    def from_env(cls) -> "TrafikoaClient":
        return cls(
            base_url=settings.trafikoa_base_url,
            api_key=settings.trafikoa_api_key,
        )

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = requests.get(
            f"{self.base_url}/{path.lstrip('/')}",
            params=params,
            headers=headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def get_paginated(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> list[Any]:
        page = int((params or {}).get("_page", 1))
        base_params = {key: value for key, value in (params or {}).items() if key != "_page"}
        payloads = []

        while True:
            request_params = dict(base_params)
            if page > 1:
                request_params["_page"] = page

            payload = self.get(path, params=request_params or None)
            payloads.append(payload)

            total_pages = _extract_total_pages(payload)
            if total_pages is None or page >= total_pages:
                break

            page += 1

        return payloads


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
