import json
import re
import unicodedata
from typing import Any

from src.config import settings
from src.rag.ollama_client import OllamaClient
from src.rag.query_understanding import (
    INTENT_CAMARAS,
    INTENT_CONGESTION,
    QueryUnderstanding,
    understand_query,
)
from src.rag.retriever import retrieve_with_diagnostics
from src.trafikoa.camera_search import normalize_text, search_cameras

NO_EVIDENCE_MESSAGE = "No encontré información suficiente en las fuentes disponibles."
NO_CAMERA_MESSAGE = "No encontré cámaras para ese lugar o carretera en las fuentes disponibles."
NO_SPECIFIC_LOCATION_MESSAGE = (
    "No encontré información específica para esa ubicación en las fuentes disponibles."
)
ROUTE_LIMITATION_MESSAGE = (
    "No dispongo de cálculo de ruta completo, pero encontré información relacionada "
    "con las entidades de la pregunta."
)

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

    query_context = understand_query(question)
    debug_payload = {"query_understanding": query_context.to_dict()}

    camera_answer = _answer_camera_question(question, query_context)
    if camera_answer is not None:
        camera_answer.update(debug_payload)
        return camera_answer

    retrieval = retrieve_with_diagnostics(
        question,
        k or settings.rag_top_k,
        query_understanding=query_context,
        candidate_k=20,
    )
    results = retrieval["results"]
    useful_results = [result for result in results if result.get("text")]
    if not useful_results:
        return {
            "answer": _no_results_message(query_context),
            "sources": [],
            **debug_payload,
            "retrieval": _retrieval_debug(retrieval),
        }

    structured_results = _select_structured_results(query_context, useful_results)
    if structured_results:
        return {
            "answer": _build_structured_answer(
                structured_results,
                query_context=query_context,
                retrieval=retrieval,
            ),
            "sources": _sources_from_results(structured_results),
            **debug_payload,
            "retrieval": _retrieval_debug(retrieval),
        }

    context = _build_context(useful_results)
    prompt = _build_prompt(question, context)
    answer = OllamaClient().generate(prompt=prompt, system=SYSTEM_PROMPT)
    if _is_no_evidence_answer(answer):
        return {
            "answer": _no_results_message(query_context),
            "sources": [],
            **debug_payload,
            "retrieval": _retrieval_debug(retrieval),
        }

    answer = _prepend_caveats(answer, query_context, retrieval)
    return {
        "answer": answer,
        "sources": _sources_from_results(useful_results),
        **debug_payload,
        "retrieval": _retrieval_debug(retrieval),
    }


def _answer_camera_question(
    question: str,
    query_context: QueryUnderstanding,
) -> dict[str, Any] | None:
    if not _is_camera_intent(question, query_context):
        return None

    filters = _camera_filters_from_question(question, query_context)
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


def _is_camera_intent(question: str, query_context: QueryUnderstanding) -> bool:
    if query_context.intent == INTENT_CAMARAS:
        return True

    normalized_question = normalize_text(question)
    terms = set(normalized_question.split())
    if terms & CAMERA_INTENT_TERMS:
        return True

    has_show_verb = any(
        term in terms for term in {"ver", "mostrar", "muestra", "muestrame"}
    )
    has_road = CAMERA_ROAD_PATTERN.search(normalized_question) is not None
    return has_show_verb and has_road


def _camera_filters_from_question(
    question: str,
    query_context: QueryUnderstanding,
) -> dict[str, str | None]:
    normalized_question = normalize_text(question)
    road = query_context.carreteras[0] if query_context.carreteras else None
    road = road or _extract_camera_road(normalized_question)
    province = _extract_camera_province(normalized_question)
    place = query_context.lugares[0] if query_context.lugares else None
    free_text = place or _extract_camera_free_text(normalized_question)

    if road:
        free_text = None
    if province:
        free_text = None

    return {
        "q": free_text,
        "municipio": place if place and not road and not province else None,
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
    metadata["source"] = "Trafikoa"
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
    query_context: QueryUnderstanding,
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    structured_types = {"incidencia", "congestion", "camara", CORPUS_DOCUMENT_TYPE}
    structured_results = [
        result
        for result in results
        if result.get("metadata", {}).get("document_type") in structured_types
    ]
    if query_context.intent != INTENT_CAMARAS:
        non_camera_results = [
            result
            for result in structured_results
            if result.get("metadata", {}).get("document_type") != "camara"
        ]
        if non_camera_results:
            structured_results = non_camera_results

    if query_context.source_preference:
        source_results = [
            result
            for result in structured_results
            if result.get("metadata", {}).get("source") == query_context.source_preference
            or result.get("metadata", {}).get("fuente") == query_context.source_preference
        ]
        if source_results:
            structured_results = source_results

    return structured_results


def _build_structured_answer(
    results: list[dict[str, Any]],
    query_context: QueryUnderstanding,
    retrieval: dict[str, Any],
) -> str:
    lines = _answer_caveats(query_context, retrieval, results)
    lines.append("Encontré estos elementos en las fuentes disponibles:")

    groups = _group_results_by_type(results)
    for title in ["Incidencias", "Obras/cortes", "Congestión", "Cámaras", "Corpus multifuente"]:
        group_results = groups.get(title, [])
        if not group_results:
            continue
        lines.append("")
        lines.append(f"{title}:")
        for index, result in enumerate(group_results, start=1):
            metadata = result.get("metadata", {})
            lines.extend(_format_structured_result(index, metadata))

    return "\n".join(lines).strip()

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


def _answer_caveats(
    query_context: QueryUnderstanding,
    retrieval: dict[str, Any],
    results: list[dict[str, Any]],
) -> list[str]:
    lines = []
    if query_context.is_route:
        route_label = " - ".join(
            place
            for place in [query_context.route_from, query_context.route_to]
            if place
        )
        if route_label:
            lines.append(
                "No dispongo de cálculo de ruta completo para "
                f"{route_label}, pero encontré información relacionada."
            )
        else:
            lines.append(ROUTE_LIMITATION_MESSAGE)

    if retrieval.get("fallback_used") and (
        query_context.lugares or query_context.carreteras
    ):
        lines.append(
            NO_SPECIFIC_LOCATION_MESSAGE
            + " Muestro solo coincidencias relacionadas, no una confirmación exacta."
        )

    if query_context.intent == INTENT_CONGESTION and not _has_document_type(
        results,
        "congestion",
    ):
        lines.append(
            "No encontré registros de congestión específicos para esa ubicación o ruta."
        )

    if lines:
        lines.append("")
    return lines


def _prepend_caveats(
    answer: str,
    query_context: QueryUnderstanding,
    retrieval: dict[str, Any],
) -> str:
    caveats = _answer_caveats(query_context, retrieval, [])
    if not caveats:
        return answer
    return "\n".join(caveats + [answer]).strip()


def _group_results_by_type(results: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {
        "Incidencias": [],
        "Obras/cortes": [],
        "Congestión": [],
        "Cámaras": [],
        "Corpus multifuente": [],
    }
    for result in results:
        metadata = result.get("metadata", {})
        document_type = metadata.get("document_type")
        if document_type == "incidencia":
            groups["Incidencias"].append(result)
        elif document_type == "congestion":
            groups["Congestión"].append(result)
        elif document_type == "camara":
            groups["Cámaras"].append(result)
        elif document_type == CORPUS_DOCUMENT_TYPE and _is_works_or_closure(metadata):
            groups["Obras/cortes"].append(result)
        elif document_type == CORPUS_DOCUMENT_TYPE:
            groups["Corpus multifuente"].append(result)
    return groups


def _is_works_or_closure(metadata: dict[str, Any]) -> bool:
    haystack = _normalize(
        " ".join(
            str(metadata.get(field) or "")
            for field in ["tipo", "tipo_evento", "title", "text"]
        )
    )
    return any(
        term in haystack
        for term in ["obra", "corte", "cortado", "carril", "paso alternativo", "ocupacion"]
    )


def _has_document_type(results: list[dict[str, Any]], document_type: str) -> bool:
    return any(
        result.get("metadata", {}).get("document_type") == document_type
        for result in results
    )


def _no_results_message(query_context: QueryUnderstanding) -> str:
    if query_context.is_route:
        return (
            "No dispongo de cálculo de ruta completo y no encontré información "
            "específica para esa ruta en las fuentes disponibles."
        )
    if query_context.lugares or query_context.carreteras:
        return NO_SPECIFIC_LOCATION_MESSAGE
    return NO_EVIDENCE_MESSAGE


def _retrieval_debug(retrieval: dict[str, Any]) -> dict[str, Any]:
    return {
        "fallback_used": retrieval.get("fallback_used", False),
        "strict_result_count": retrieval.get("strict_result_count", 0),
        "candidate_count": retrieval.get("candidate_count", 0),
        "filters": retrieval.get("filters", {}),
    }


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
                "rerank_score": result.get("rerank_score"),
                "entity_matches": result.get("entity_matches", []),
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
