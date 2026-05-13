import unicodedata
from typing import Any

from src.config import settings
from src.rag.index_manager import get_index_status


CAPABILITY_PATTERNS = [
    "que sabes",
    "sobre que sabes",
    "que informacion tienes",
    "sobre que informacion tienes",
    "sobre que tienes conocimiento",
    "sobre que te puedo preguntar",
    "que te puedo preguntar",
    "que fuentes",
    "fuentes de informacion",
    "de donde sale la informacion",
    "de donde salen los datos",
    "que datos usas",
    "que puedes responder",
    "que puedes contestar",
    "puedes calcular rutas",
    "calculas rutas",
    "calcular rutas",
]


def is_capabilities_question(question: str) -> bool:
    normalized_question = _normalize(question)
    return any(pattern in normalized_question for pattern in CAPABILITY_PATTERNS)


def build_capabilities_answer(question: str = "") -> str:
    status = _safe_index_status()
    documents_indexed = _to_int(status.get("documents_indexed"))
    document_type_counts = _clean_counts(status.get("document_type_counts"))
    source_counts = _clean_counts(status.get("source_counts"))
    last_refresh_at = str(status.get("last_refresh_at") or "").strip()

    lines = []
    if "ruta" in _normalize(question):
        lines.append(
            "No calculo rutas completas ni todos los tramos entre un origen y un "
            "destino. Sí puedo buscar información relacionada con carreteras, "
            "municipios, cortes, incidencias, cámaras o congestión en las fuentes "
            "disponibles."
        )

    lines.append(
        "Puedes preguntarme sobre movilidad urbana en Euskadi y Bilbao. "
        "Trabajo con incidencias de Trafikoa, cámaras de tráfico, registros "
        "de congestión basados en flows/meters, avisos institucionales del "
        "Ayuntamiento de Bilbao y afecciones de tráfico publicadas por "
        "DEIA - Bizkaimove."
    )

    bluesky_count = source_counts.get("Bluesky", 0)
    if bluesky_count:
        lines.append(
            "También tengo publicaciones seleccionadas de Bluesky relacionadas "
            f"con movilidad o tráfico; ahora mismo hay {bluesky_count} documentos "
            "de Bluesky en el índice."
        )
    elif settings.bluesky_handle and settings.bluesky_app_password:
        lines.append(
            "Bluesky está configurado, pero depende de las cuentas seguidas y de "
            "la actividad reciente; en el índice actual no aparecen documentos "
            "de Bluesky."
        )
    else:
        lines.append(
            "Bluesky puede incorporarse si hay credenciales y publicaciones "
            "relevantes, pero depende de las cuentas seguidas y de la actividad "
            "reciente."
        )

    index_sentence = _index_status_sentence(
        documents_indexed=documents_indexed,
        document_type_counts=document_type_counts,
        last_refresh_at=last_refresh_at,
    )
    if index_sentence:
        lines.append(index_sentence)

    lines.append(
        "Uso ChromaDB para recuperar documentos por similitud semántica y reglas "
        "de filtrado por intención, carretera, lugar y fuente. La generación se "
        f"hace en local con Ollama y el modelo {settings.ollama_model}, sin APIs "
        "pagas."
    )
    lines.append(
        "Puedes hacer preguntas como: '¿Hay incidencias en la A-8?', 'Muéstrame "
        "cámaras en Bilbao', '¿Qué cortes hay en Alameda Recalde?' o '¿Qué obras "
        "aparecen en Bizkaimove?'."
    )
    lines.append(
        "Limitaciones: no calculo rutas completas, no hago predicciones oficiales "
        "y no invento información fuera de las fuentes disponibles. Si no hay "
        "datos sobre una zona, carretera o fuente, debo decirlo."
    )

    return "\n\n".join(lines)


def _safe_index_status() -> dict[str, Any]:
    try:
        return get_index_status()
    except Exception:
        return {}


def _index_status_sentence(
    documents_indexed: int,
    document_type_counts: dict[str, int],
    last_refresh_at: str,
) -> str:
    pieces = []
    if documents_indexed:
        pieces.append(f"El índice RAG contiene {documents_indexed} documentos")
    else:
        pieces.append("No he podido confirmar el número actual de documentos del índice")

    if document_type_counts:
        pieces.append(
            "repartidos en "
            + ", ".join(
                f"{document_type}: {count}"
                for document_type, count in sorted(document_type_counts.items())
            )
        )

    sentence = " ".join(pieces)
    if last_refresh_at:
        sentence += f". Última actualización registrada: {last_refresh_at}"
    return sentence + "."


def _clean_counts(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    clean_counts = {}
    for key, count in value.items():
        parsed_count = _to_int(count)
        if parsed_count:
            clean_counts[str(key)] = parsed_count
    return clean_counts


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value).strip().lower())
    without_accents = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return " ".join(without_accents.split())
