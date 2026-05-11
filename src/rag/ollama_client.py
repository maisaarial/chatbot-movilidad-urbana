from typing import Any

import requests

from src.config import settings


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(
        self,
        base_url: str = settings.ollama_base_url,
        model: str = settings.ollama_model,
        timeout: int = settings.ollama_timeout,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def generate(self, prompt: str, system: str | None = None) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 220,
            },
        }
        if system:
            payload["system"] = system

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=(3, self.timeout),
            )
        except requests.ConnectionError as exc:
            raise OllamaError(
                "No se pudo conectar con Ollama en "
                f"{self.base_url}. Instala/arranca Ollama y ejecuta: "
                f"ollama pull {self.model}"
            ) from exc
        except requests.Timeout as exc:
            raise OllamaError("La llamada a Ollama supero el tiempo de espera.") from exc
        except requests.RequestException as exc:
            raise OllamaError(f"Error llamando a Ollama: {exc}") from exc

        if response.status_code == 404:
            raise OllamaError(
                f"Ollama no encontro el modelo '{self.model}'. Ejecuta: "
                f"ollama pull {self.model}"
            )
        if response.status_code >= 400:
            detail = _extract_error(response)
            if "model" in detail.lower() and "not found" in detail.lower():
                raise OllamaError(
                    f"Ollama no encontro el modelo '{self.model}'. Ejecuta: "
                    f"ollama pull {self.model}"
                )
            raise OllamaError(f"Ollama devolvio HTTP {response.status_code}: {detail}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise OllamaError("Ollama devolvio una respuesta no JSON.") from exc

        answer = payload.get("response")
        if not answer:
            raise OllamaError("Ollama no devolvio texto de respuesta.")
        return str(answer).strip()


def _extract_error(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text
    return str(payload.get("error") or payload)
