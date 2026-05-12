import json
import re
import unicodedata
from typing import Any

from src.config import settings
from src.rag.ollama_client import OllamaClient
from src.rag.retriever import retrieve
from src.trafikoa.camera_search import normalize_text, search_cameras

NO_EVIDENCE_MESSAGE = "No encontré información suficiente en las fuentes disponibles."
NO_CAMERA_MESSAGE = "No encontré cámaras para ese lugar o carretera en las fuentes disponibles."

CAMERA_ROAD_PATTERN = re.compile(r"\b(?:a|ap|bi|gi|n)-\s*\d+[a-z]?\b", re.IGNORECASE)
CAMERA_INTENT_TERMS = {
    "camara",
    "camaras",
    "camera",
    "cameras",
    "cctv",
    "webcam",
    "imagen",
    "imagenes",
}
CAMERA_PROVINCES = {
    "bizkaia": "Bizkaia",
    "gipuzkoa": "Gipuzkoa",
    "araba": "Alava-Araba",
    "alava": "Alava-Araba",
}
CAMERA_QUERY_STOPWORDS = {
    "camara",
    "camaras",
    "camera",
    "cameras",
    "cctv",
    "webcam",
    "imagen",
    "imagenes",
    "muestrame",
    "muestra",
    "mostrar",
    "ver",
    "que",
    "cuales",
    "hay",
    "cerca",
    "de",
    "del",
    "en",
    "la",
    "el",
    "las",
    "los",
    "por",
    "para",
    "una",
    "un",
}
CORPUS_DOCUMENT_TYPE = "corpus_multifuente"
CORPUS_SOURCE_ALIASES = {
    "ayuntamiento de bilbao": "Ayuntamiento de Bilbao",
    "deia": "DEIA - Bizkaimove",
    "bizkaimove": "DEIA - Bizkaimove",
    "bluesky": "Bluesky",
}

SYSTEM_PROMPT = """
Eres un asistente de movilidad urbana. Responde SOLO usando el contexto recuperado.
No uses conocimiento externo, suposiciones ni datos inventados.
No respondas de forma generica si las fuentes contienen detalles concretos.
Si el contexto no contiene evidencia suficiente para responder, responde exactamente:
No encontré información suficiente en las fuentes disponibles.
Cuando haya evidencia, enumera los elementos encontrados y cita sus campos disponibles.

Reglas de contenido:
- Para incidencias, incluye carretera, tipo, causa, sentido, municipio, provincia y timestamp.
- Para congestion, incluye carretera o medidor, nivel de congestion, valor_trafico, unidad, municipio, provincia y timestamp.
- Para camaras, incluye nombre, carretera, municipio, provincia e image_url o source_url.
- Para corpus multifuente, menciona source, source_type, title, tipo_evento, timestamp y URL si existen.
- Para Bluesky, indica que es una publicacion social y menciona el autor si esta disponible.
- Si un campo solicitado no aparece en la fuente, escribe "no disponible" para ese campo.
- No digas solo "si, hay varias"; debes listar cuales son.
- Mantente fiel a las fuentes recuperadas y no agregues explicaciones externas.
"""


def answer_question(question: str, k: int | None = None) -> dict[str, Any]:
    question = question.strip()
    if not question:
        return {"answer": NO_EVIDENCE_MESSAGE, "sources": []}

    camera_answer = _answer_camera_question(question)
    if camera_answer is not None:
        return camera_answer

    results = retrieve(question, k or settings.rag_top_k)
    useful_results = [result for result in results if result.get("text")]
    if not useful_results:
        return {"answer": NO_EVIDENCE_MESSAGE, "sources": []}

    structured_results = _select_structured_results(question, useful_results)
    if structured_results:
        return {
            "answer": _build_structured_answer(structured_results),
            "sources": _sources_from_results(structured_results),
        }

    context = _build_context(useful_results)
    prompt = _build_prompt(question, context)
    answer = OllamaClient().generate(prompt=prompt, system=SYSTEM_PROMPT)
    if _is_no_evidence_answer(answer):
        return {"answer": NO_EVIDENCE_MESSAGE, "sources": []}

    return {
        "answer": answer,
        "sources": _sources_from_results(useful_results),
    }


def _answer_camera_question(question: str) -> dict[str, Any] | None:
    if not _is_camera_intent(question):
        return None

    filters = _camera_filters_from_question(question)
    cameras = search_cameras(
        q=filters.get("q"),
        municipio=filters.get("municipio"),
        carretera=filters.get("carretera"),
        provincia=filters.get("provincia"),
        limit=10,
        only_with_image=True,
    )
    only_without_image = False
    if not cameras:
        cameras = search_cameras(
            q=filters.get("q"),
            municipio=filters.get("municipio"),
            carretera=filters.get("carretera"),
            provincia=filters.get("provincia"),
            limit=10,
            only_with_image=False,
        )
        only_without_image = bool(cameras)

    if not cameras:
        return {"answer": NO_CAMERA_MESSAGE, "sources": []}

    return {
        "answer": _build_camera_answer(cameras, only_without_image=only_without_image),
        "sources": [_camera_to_source(camera) for camera in cameras],
    }


def _is_camera_intent(question: str) -> bool:
    normalized_question = normalize_text(question)
    terms = set(normalized_question.split())
    if terms & CAMERA_INTENT_TERMS:
        return True

    has_show_verb = any(
        term in terms for term in {"ver", "mostrar", "muestra", "muestrame"}
    )
    has_road = CAMERA_ROAD_PATTERN.search(normalized_question) is not None
    return has_show_verb and has_road


def _camera_filters_from_question(question: str) -> dict[str, str | None]:
    normalized_question = normalize_text(question)
    road = _extract_camera_road(normalized_question)
    province = _extract_camera_province(normalized_question)
    free_text = _extract_camera_free_text(normalized_question)

    if road:
        free_text = None
    if province:
        free_text = None

    return {
        "q": free_text,
        "municipio": None,
        "carretera": road,
        "provincia": province,
    }


def _extract_camera_road(normalized_question: str) -> str | None:
    match = CAMERA_ROAD_PATTERN.search(normalized_question)
    if not match:
        return None
    return match.group(0).upper().replace(" ", "")


def _extract_camera_province(normalized_question: str) -> str | None:
    for normalized_province, province in CAMERA_PROVINCES.items():
        if normalized_province in normalized_question.split():
            return province
    return None


def _extract_camera_free_text(normalized_question: str) -> str | None:
    cleaned = CAMERA_ROAD_PATTERN.sub(" ", normalized_question)
    tokens = [
        token
        for token in cleaned.split()
        if token not in CAMERA_QUERY_STOPWORDS and len(token) > 1
    ]
    if not tokens:
        return None
    return " ".join(tokens)


def _build_camera_answer(
    cameras: list[dict[str, Any]],
    only_without_image: bool = False,
) -> str:
    lines = ["Sí. Encontré estas cámaras:"]
    if only_without_image:
        lines.append(
            "Las cámaras encontradas existen en la API, pero no tienen imagen disponible."
        )
    for index, camera in enumerate(cameras, start=1):
        image_url = camera.get("image_url") or "no hay imagen disponible"
        maps_url = camera.get("maps_url") or "no disponible"
        lines.extend(
            [
                f"{index}. Nombre: {_value_or_unavailable(camera.get('nombre'))}",
                f"   Carretera: {_value_or_unavailable(camera.get('carretera'))}",
                (
                    "   Municipio/provincia: "
                    f"{_value_or_unavailable(camera.get('municipio'))} / "
                    f"{_value_or_unavailable(camera.get('provincia'))}"
                ),
                f"   Imagen: {image_url}",
                f"   Mapa: {maps_url}",
            ]
        )
    return "\n".join(lines)


def _camera_to_source(camera: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(camera)
    metadata["document_type"] = "camara"
    metadata["tipo"] = "camara"
    return {
        "text": (
            f"Cámara {camera.get('nombre') or 'no disponible'} en "
            f"{camera.get('carretera') or 'no disponible'}, "
            f"{camera.get('municipio') or 'no disponible'}, "
            f"{camera.get('provincia') or 'no disponible'}."
        ),
        "score": 1.0,
        "distance": 0.0,
        "metadata": metadata,
    }


def _build_context(results: list[dict[str, Any]]) -> str:
    blocks = []
    for index, result in enumerate(results, start=1):
        metadata = result.get("metadata", {})
        metadata_json = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
        blocks.append(
            f"[Fuente {index}]\n"
            f"Tipo de documento: {_field(metadata, 'document_type')}\n"
            f"Metadata completa: {metadata_json}\n"
            f"Texto recuperado: {result.get('text', '')}\n"
        )
    return "\n".join(blocks)


def _select_structured_results(
    question: str,
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not _has_strong_evidence(results):
        return []

    preferred_source = _preferred_corpus_source(question)
    if preferred_source:
        filtered_results = [
            result
            for result in results
            if result.get("metadata", {}).get("source") == preferred_source
        ]
        if filtered_results:
            return filtered_results

    preferred_type = _preferred_document_type(question)
    if preferred_type:
        filtered_results = [
            result
            for result in results
            if result.get("metadata", {}).get("document_type") == preferred_type
        ]
        if filtered_results:
            return filtered_results

    structured_types = {"incidencia", "congestion", "camara", CORPUS_DOCUMENT_TYPE}
    return [
        result
        for result in results
        if result.get("metadata", {}).get("document_type") in structured_types
    ]


def _has_strong_evidence(results: list[dict[str, Any]]) -> bool:
    for result in results:
        distance = result.get("distance")
        score = result.get("score")
        if distance == 0 or distance == 0.0:
            return True
        if score is not None and score >= 0.65:
            return True
    return False


def _preferred_document_type(question: str) -> str | None:
    normalized_question = _normalize(question)
    if any(
        term in normalized_question
        for term in [
            "ayuntamiento",
            "aviso",
            "avisos",
            "noticia",
            "noticias",
            "deia",
            "bizkaimove",
            "bluesky",
            "publicacion",
            "publicaciones",
            "social",
        ]
    ):
        return CORPUS_DOCUMENT_TYPE
    if any(term in normalized_question for term in ["camara", "camaras", "imagen"]):
        return "camara"
    if any(term in normalized_question for term in ["congestion", "retencion", "vehiculo", "vehiculos"]):
        return "congestion"
    if any(term in normalized_question for term in ["incidencia", "incidencias", "accidente", "averia", "obras"]):
        return "incidencia"
    return None


def _preferred_corpus_source(question: str) -> str | None:
    normalized_question = _normalize(question)
    for alias, source in CORPUS_SOURCE_ALIASES.items():
        if alias in normalized_question:
            return source
    return None


def _build_structured_answer(results: list[dict[str, Any]]) -> str:
    lines = ["Si. Segun las fuentes recuperadas, se encontraron estos elementos:"]
    for index, result in enumerate(results, start=1):
        metadata = result.get("metadata", {})
        lines.extend(_format_structured_result(index, metadata))
    return "\n".join(lines)

    document_type = results[0].get("metadata", {}).get("document_type")
    if document_type == "incidencia":
        lines = ["Sí. Según las fuentes recuperadas, se encontraron estas incidencias:"]
        for index, result in enumerate(results, start=1):
            metadata = result.get("metadata", {})
            lines.extend(
                [
                    f"{index}. Tipo: {_field(metadata, 'tipo')}",
                    f"   Carretera: {_field(metadata, 'carretera')}",
                    f"   Causa: {_field(metadata, 'causa')}",
                    f"   Sentido: {_field(metadata, 'sentido')}",
                    (
                        "   Municipio/provincia: "
                        f"{_field(metadata, 'municipio')} / {_field(metadata, 'provincia')}"
                    ),
                    f"   Fecha/hora: {_field(metadata, 'timestamp')}",
                ]
            )
        return "\n".join(lines)

    if document_type == "congestion":
        lines = ["Sí. Según las fuentes recuperadas, se encontraron estos registros de congestión:"]
        for index, result in enumerate(results, start=1):
            metadata = result.get("metadata", {})
            lines.extend(
                [
                    f"{index}. Nivel: {_field(metadata, 'congestion')}",
                    f"   Carretera o medidor: {_field(metadata, 'carretera')}",
                    (
                        "   Valor de tráfico: "
                        f"{_field(metadata, 'valor_trafico')} {_field(metadata, 'unidad')}"
                    ),
                    (
                        "   Municipio/provincia: "
                        f"{_field(metadata, 'municipio')} / {_field(metadata, 'provincia')}"
                    ),
                    f"   Fecha/hora: {_field(metadata, 'timestamp')}",
                ]
            )
        return "\n".join(lines)

    if document_type == "camara":
        lines = ["Sí. Según las fuentes recuperadas, se encontraron estas cámaras:"]
        for index, result in enumerate(results, start=1):
            metadata = result.get("metadata", {})
            lines.extend(
                [
                    f"{index}. Nombre: {_field(metadata, 'nombre')}",
                    f"   Carretera: {_field(metadata, 'carretera')}",
                    (
                        "   Municipio/provincia: "
                        f"{_field(metadata, 'municipio')} / {_field(metadata, 'provincia')}"
                    ),
                    f"   Image URL: {_field(metadata, 'image_url')}",
                    f"   Source URL: {_field(metadata, 'source_url')}",
                ]
            )
        return "\n".join(lines)

    lines = ["Sí. Según las fuentes recuperadas, se encontraron estos elementos:"]
    for index, result in enumerate(results, start=1):
        metadata = result.get("metadata", {})
        lines.extend(
            [
                f"{index}. Tipo: {_field(metadata, 'tipo')}",
                f"   Carretera: {_field(metadata, 'carretera')}",
                (
                    "   Municipio/provincia: "
                    f"{_field(metadata, 'municipio')} / {_field(metadata, 'provincia')}"
                ),
                f"   Fecha/hora: {_field(metadata, 'timestamp')}",
            ]
        )
    return "\n".join(lines)


def _format_structured_result(index: int, metadata: dict[str, Any]) -> list[str]:
    document_type = metadata.get("document_type")
    if document_type == "incidencia":
        return [
            f"{index}. Fuente: {_field(metadata, 'source')}",
            f"   Tipo: {_field(metadata, 'tipo')}",
            f"   Carretera: {_field(metadata, 'carretera')}",
            f"   Causa: {_field(metadata, 'causa')}",
            f"   Sentido: {_field(metadata, 'sentido')}",
            (
                "   Municipio/provincia: "
                f"{_field(metadata, 'municipio')} / {_field(metadata, 'provincia')}"
            ),
            f"   Fecha/hora: {_field(metadata, 'timestamp')}",
        ]

    if document_type == "congestion":
        return [
            f"{index}. Fuente: {_field(metadata, 'source')}",
            f"   Nivel: {_field(metadata, 'congestion')}",
            f"   Carretera o medidor: {_field(metadata, 'carretera')}",
            (
                "   Valor de trafico: "
                f"{_field(metadata, 'valor_trafico')} {_field(metadata, 'unidad')}"
            ),
            (
                "   Municipio/provincia: "
                f"{_field(metadata, 'municipio')} / {_field(metadata, 'provincia')}"
            ),
            f"   Fecha/hora: {_field(metadata, 'timestamp')}",
        ]

    if document_type == "camara":
        return [
            f"{index}. Fuente: {_field(metadata, 'source')}",
            f"   Nombre: {_field(metadata, 'nombre')}",
            f"   Carretera: {_field(metadata, 'carretera')}",
            (
                "   Municipio/provincia: "
                f"{_field(metadata, 'municipio')} / {_field(metadata, 'provincia')}"
            ),
            f"   Image URL: {_field(metadata, 'image_url')}",
            f"   Source URL: {_field(metadata, 'source_url')}",
        ]

    if document_type == CORPUS_DOCUMENT_TYPE:
        source = _field(metadata, "source")
        prefix = "Publicacion social" if source == "Bluesky" else "Documento multifuente"
        lines = [
            f"{index}. {prefix}: {source}",
            f"   Tipo de fuente: {_field(metadata, 'source_type')}",
            f"   Titulo: {_field(metadata, 'title')}",
            f"   Tipo de evento: {_field(metadata, 'tipo_evento')}",
            (
                "   Municipio/provincia: "
                f"{_field(metadata, 'municipio')} / {_field(metadata, 'provincia')}"
            ),
            f"   Carretera: {_field(metadata, 'carretera')}",
            f"   Fecha/hora: {_field(metadata, 'timestamp')}",
            f"   URL: {_field(metadata, 'url')}",
        ]
        if source == "Bluesky":
            lines.insert(3, f"   Autor: {_field(metadata, 'author')}")
        return lines

    return [
        f"{index}. Fuente: {_field(metadata, 'source')}",
        f"   Tipo: {_field(metadata, 'tipo')}",
        f"   Carretera: {_field(metadata, 'carretera')}",
        (
            "   Municipio/provincia: "
            f"{_field(metadata, 'municipio')} / {_field(metadata, 'provincia')}"
        ),
        f"   Fecha/hora: {_field(metadata, 'timestamp')}",
    ]


def _build_prompt(question: str, context: str) -> str:
    return (
        "Contexto recuperado:\n"
        f"{context}\n\n"
        "Formato obligatorio si la pregunta tiene respuesta:\n"
        "Si. Segun las fuentes recuperadas, se encontraron estos elementos:\n"
        "1. Tipo: ...\n"
        "   Carretera: ...\n"
        "   Causa, nivel o nombre: ...\n"
        "   Sentido, valor o image_url: ...\n"
        "   Municipio/provincia: ...\n"
        "   Fecha/hora: ...\n\n"
        "Pregunta del usuario:\n"
        f"{question}\n\n"
        "Respuesta:"
    )


def _field(metadata: dict[str, Any], key: str) -> str:
    return _value_or_unavailable(metadata.get(key))


def _value_or_unavailable(value: Any) -> str:
    if value is None or str(value).strip() == "":
        return "no disponible"
    return str(value)


def _sources_from_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources = []
    for result in results:
        metadata = result.get("metadata", {})
        sources.append(
            {
                "text": result.get("text"),
                "score": result.get("score"),
                "distance": result.get("distance"),
                "metadata": metadata,
            }
        )
    return sources


def _is_no_evidence_answer(answer: str) -> bool:
    expected = _normalize(NO_EVIDENCE_MESSAGE)
    actual = _normalize(answer)
    return actual.startswith(expected)


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip().lower())
    return "".join(char for char in normalized if not unicodedata.combining(char))
