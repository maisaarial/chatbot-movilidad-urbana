import json
import re
import unicodedata
from typing import Any

from src.config import settings
from src.rag.capabilities import build_capabilities_answer, is_capabilities_question
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
Cuando haya evidencia, redacta una respuesta natural y útil para el usuario.

Reglas de contenido:
- No copies metadata completa ni menciones source_type, document_type o "Documento multifuente".
- Para incidencias, resume que ocurre, carretera, causa, sentido, municipio y fecha si aportan valor.
- Para congestion, resume nivel, medidor/carretera, municipio, valor y fecha si aportan valor.
- Para camaras, resume nombre, carretera, municipio y enlace solo si es necesario.
- Para avisos, obras o cortes, resume fuente, afeccion, calle/carretera, sentido, municipio y fecha si aportan valor.
- Si un campo solicitado no aparece en la fuente, no lo presentes como si existiera.
- No digas solo "si, hay varias"; debes listar cuales son.
- Mantente fiel a las fuentes recuperadas y no agregues explicaciones externas.
"""


def answer_question(question: str, k: int | None = None) -> dict[str, Any]:
    question = question.strip()
    if not question:
        return {"answer": NO_EVIDENCE_MESSAGE, "sources": []}

    if is_capabilities_question(question):
        return {"answer": build_capabilities_answer(question), "sources": []}

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
    groups = _group_results_by_type(results)

    summaries = []
    for title, formatter in [
        ("Incidencias", _summarize_incidents),
        ("Obras/cortes", _summarize_works_or_closures),
        ("Congestión", _summarize_congestion),
        ("Cámaras", _summarize_cameras),
        ("Avisos/noticias", _summarize_notices),
    ]:
        group_results = groups.get(title, [])
        if not group_results:
            continue
        summary = formatter(group_results, query_context)
        if summary:
            summaries.append((title, summary))

    if not summaries:
        lines.append(NO_EVIDENCE_MESSAGE)
    elif len(summaries) == 1:
        lines.append(summaries[0][1])
    else:
        for title, summary in summaries:
            lines.append(f"{title}: {summary}")

    return "\n".join(lines).strip()


def _summarize_incidents(
    results: list[dict[str, Any]],
    query_context: QueryUnderstanding,
) -> str:
    phrases = _unique_phrases(
        _incident_phrase(result.get("metadata", {})) for result in results
    )
    if not phrases:
        return ""

    location = _query_location_label(query_context) or _result_location_label(
        results[0].get("metadata", {})
    )
    prefix = "Sí."
    if location:
        if query_context.carreteras and location == query_context.carreteras[0]:
            prefix += f" En la {location} se "
        else:
            prefix += f" En {location} se "
    else:
        prefix += " Se "

    if len(phrases) == 1:
        return f"{prefix}encontró {phrases[0]}."
    return f"{prefix}encontraron varias incidencias: {_join_phrases(phrases)}."


def _incident_phrase(metadata: dict[str, Any]) -> str:
    incident_type = _clean_value(metadata.get("tipo"))
    cause = _clean_value(metadata.get("causa"))
    sense = _clean_value(metadata.get("sentido"))
    municipality = _clean_value(metadata.get("municipio"))
    road = _clean_value(metadata.get("carretera"))

    if incident_type and "puerto" in _normalize(incident_type):
        phrase = "registros de puerto de montaña"
    elif incident_type:
        phrase = f"{_article_for(incident_type)} {_lower_first(incident_type)}"
    else:
        phrase = "una incidencia"

    details = []
    if cause and _normalize(cause) not in {"desconocida", "desconocido"}:
        details.append(f"por {_lower_first(cause)}")
    elif incident_type and "puerto" in _normalize(incident_type):
        details.append("sin causa detallada")
    if sense:
        details.append(f"en sentido {_title_like(sense)}")
    if municipality:
        details.append(f", en {_title_like(municipality)}" if sense else f"en {_title_like(municipality)}")
    elif road and "puerto" not in _normalize(incident_type or ""):
        details.append(f"en la {road}")

    return " ".join([phrase] + details).replace(" ,", ",")


def _summarize_works_or_closures(
    results: list[dict[str, Any]],
    query_context: QueryUnderstanding,
) -> str:
    phrases = _unique_phrases(
        _work_or_closure_phrase(result.get("metadata", {}), query_context)
        for result in results
    )
    if not phrases:
        return ""

    first_metadata = results[0].get("metadata", {})
    source = _clean_value(first_metadata.get("source") or first_metadata.get("fuente"))
    timestamp = _clean_value(first_metadata.get("timestamp"))

    if len(phrases) == 1:
        source_text = f"{_source_subject(source)} informa de " if source else "Se informa de "
        answer = f"Sí. {source_text}{phrases[0]}."
        if timestamp:
            answer += f" El aviso está fechado el {timestamp}."
        return answer

    source_name = "Bizkaimove" if source == "DEIA - Bizkaimove" else source
    if source_name:
        return (
            f"{source_name} recoge varias afecciones de obra o cortes. "
            f"Entre ellas: {_join_phrases(phrases)}."
        )
    return f"Se encontraron varias afecciones de obra o cortes: {_join_phrases(phrases)}."


def _work_or_closure_phrase(
    metadata: dict[str, Any],
    query_context: QueryUnderstanding,
) -> str:
    title = _clean_value(metadata.get("title"))
    event_type = _clean_value(metadata.get("tipo_evento") or metadata.get("tipo"))
    municipality = _clean_value(metadata.get("municipio"))
    road = _clean_value(metadata.get("carretera"))
    text = _clean_value(metadata.get("text"))

    event = _event_label_from_title(title) or _event_label_from_type(event_type)
    place = _place_from_query_or_title(query_context, title, text)
    sense = _sense_from_title(title) or _sense_from_text(text)

    phrase = event
    if place:
        phrase += f" en {place}"
    elif municipality:
        phrase += f" en {_title_like(municipality)}"
    if road:
        phrase += f" en la {road}"
    if sense and _is_single_specific_request(query_context):
        phrase += f", en sentido {_title_like(sense)}"

    return phrase


def _summarize_congestion(
    results: list[dict[str, Any]],
    query_context: QueryUnderstanding,
) -> str:
    phrases = _unique_phrases(
        _congestion_phrase(result.get("metadata", {})) for result in results
    )
    if not phrases:
        return ""

    location = _query_location_label(query_context)
    if len(phrases) == 1:
        if location:
            return f"Sí. Para {location} se encontró {phrases[0]}."
        return f"Sí. Se encontró {phrases[0]}."
    if location:
        return f"Para {location} se encontraron varios registros de congestión: {_join_phrases(phrases)}."
    return f"Se encontraron varios registros de congestión: {_join_phrases(phrases)}."


def _congestion_phrase(metadata: dict[str, Any]) -> str:
    level = _clean_value(metadata.get("congestion"))
    road = _clean_value(metadata.get("carretera"))
    municipality = _clean_value(metadata.get("municipio"))
    value = _clean_value(metadata.get("valor_trafico"))
    unit = _clean_value(metadata.get("unidad"))
    timestamp = _clean_value(metadata.get("timestamp"))

    phrase = f"congestión {level}" if level else "un registro de congestión"
    details = []
    if road:
        details.append(f"en {road}")
    if municipality:
        details.append(f"en {_title_like(municipality)}")
    if value and unit:
        details.append(f"con {value} {unit}")
    if timestamp:
        details.append(f"el {timestamp}")
    return " ".join([phrase] + details)


def _summarize_cameras(
    results: list[dict[str, Any]],
    query_context: QueryUnderstanding,
) -> str:
    phrases = _unique_phrases(
        _camera_phrase(result.get("metadata", {})) for result in results
    )
    if not phrases:
        return ""
    location = _query_location_label(query_context)
    if location:
        return f"Se encontraron cámaras relacionadas con {location}: {_join_phrases(phrases)}."
    return f"Se encontraron cámaras: {_join_phrases(phrases)}."


def _camera_phrase(metadata: dict[str, Any]) -> str:
    name = _clean_value(metadata.get("nombre")) or "cámara"
    road = _clean_value(metadata.get("carretera"))
    municipality = _clean_value(metadata.get("municipio"))
    details = []
    if road:
        details.append(f"en la {road}")
    if municipality:
        details.append(f"en {_title_like(municipality)}")
    return " ".join([name] + details)


def _summarize_notices(
    results: list[dict[str, Any]],
    query_context: QueryUnderstanding,
) -> str:
    phrases = _unique_phrases(
        _notice_phrase(result.get("metadata", {})) for result in results
    )
    if not phrases:
        return ""
    if len(phrases) == 1:
        return f"También aparece este aviso: {phrases[0]}."
    return f"También aparecen estos avisos o noticias: {_join_phrases(phrases)}."


def _notice_phrase(metadata: dict[str, Any]) -> str:
    title = _clean_value(metadata.get("title"))
    municipality = _clean_value(metadata.get("municipio"))
    timestamp = _clean_value(metadata.get("timestamp"))
    parts = [title or "aviso de movilidad"]
    if municipality:
        parts.append(f"en {_title_like(municipality)}")
    if timestamp:
        parts.append(f"fechado el {timestamp}")
    return ", ".join(parts)


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
        "Avisos/noticias": [],
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
            groups["Avisos/noticias"].append(result)
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


def _clean_value(value: Any) -> str:
    if value is None:
        return ""
    clean = str(value).strip()
    if not clean:
        return ""
    normalized = _normalize(clean)
    unavailable_values = {
        "no disponible",
        "none",
        "null",
        "nan",
        "sin datos",
        "no data",
    }
    if normalized in unavailable_values:
        return ""
    return clean


def _query_location_label(query_context: QueryUnderstanding) -> str:
    if query_context.carreteras:
        return query_context.carreteras[0]
    if query_context.is_route and query_context.route_from and query_context.route_to:
        return f"{query_context.route_from} - {query_context.route_to}"
    if query_context.lugares:
        return " y ".join(query_context.lugares[:2])
    return ""


def _result_location_label(metadata: dict[str, Any]) -> str:
    road = _clean_value(metadata.get("carretera"))
    municipality = _clean_value(metadata.get("municipio"))
    if road:
        return road
    return _title_like(municipality) if municipality else ""


def _event_label_from_title(title: str) -> str:
    normalized_title = _normalize(title)
    if "corte de dos carriles" in normalized_title:
        return "un corte de dos carriles"
    if "un carril cortado" in normalized_title:
        return "un carril cortado"
    if "sentido cortado" in normalized_title:
        return "un sentido cortado"
    if "arcen cortado" in normalized_title:
        return "un arcén cortado"
    if "paso alternativo" in normalized_title:
        return "un paso alternativo"
    if "ocupacion" in normalized_title and "aparcamiento" in normalized_title:
        return "una ocupación de aparcamiento"
    if "ocupacion" in normalized_title and "calzada" in normalized_title:
        return "una ocupación de calzada"
    if "corte" in normalized_title:
        return "un corte de tráfico"
    if "obra" in normalized_title:
        return "una obra"
    return ""


def _event_label_from_type(event_type: str) -> str:
    normalized_type = _normalize(event_type)
    if normalized_type == "paso_alternativo":
        return "un paso alternativo"
    if normalized_type in {"corte_carril", "corte_trafico"}:
        return "un corte de tráfico"
    if normalized_type == "obras":
        return "una obra"
    if event_type:
        return f"una afección de {_lower_first(event_type.replace('_', ' '))}"
    return "una afección de tráfico"


def _place_from_query_or_title(
    query_context: QueryUnderstanding,
    title: str,
    text: str,
) -> str:
    normalized_title = _normalize(title)
    normalized_text = _normalize(text)
    for place in query_context.lugares:
        if _normalize(place) in normalized_title:
            return place

    parenthesized = re.search(r"\(([^)]+)\)", title)
    if parenthesized:
        return _title_like(parenthesized.group(1))

    street_match = re.search(
        r"\b(?:en|de)\s+(alameda|calle|avenida|travesía|travesia)\s+([^,.]+)",
        title,
        flags=re.IGNORECASE,
    )
    if street_match:
        return _title_like(" ".join(street_match.groups()))

    for place in query_context.lugares:
        if _normalize(place) in normalized_text:
            return place

    return ""


def _sense_from_title(title: str) -> str:
    if _normalize(title).startswith("sentido cortado"):
        return ""
    match = re.search(r"\bsentido\s+([^,.]+)", title, flags=re.IGNORECASE)
    if not match:
        return ""
    return match.group(1).strip()


def _sense_from_text(text: str) -> str:
    match = re.search(r"\bsentido[:\s]+([^,.]+)", text, flags=re.IGNORECASE)
    if not match:
        return ""
    return match.group(1).strip()


def _unique_phrases(phrases: Any) -> list[str]:
    unique = []
    seen = set()
    for phrase in phrases:
        if not phrase:
            continue
        normalized = _normalize(phrase)
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(phrase)
    return unique


def _join_phrases(phrases: list[str], limit: int = 5) -> str:
    selected = phrases[:limit]
    if len(phrases) > limit:
        selected.append("otras afecciones relacionadas")
    if not selected:
        return ""
    if len(selected) == 1:
        return selected[0]
    if len(selected) == 2:
        return f"{selected[0]} y {selected[1]}"
    return f"{', '.join(selected[:-1])} y {selected[-1]}"


def _article_for(value: str) -> str:
    normalized = _normalize(value)
    if normalized.endswith("a") or normalized in {"averia", "incidencia"}:
        return "una"
    return "un"


def _lower_first(value: str) -> str:
    if not value:
        return ""
    return value[:1].lower() + value[1:]


def _title_like(value: str) -> str:
    if not value:
        return ""
    clean = " ".join(str(value).split())
    if clean.isupper():
        return clean.title()
    return clean[:1].upper() + clean[1:]


def _source_subject(source: str) -> str:
    if source == "Ayuntamiento de Bilbao":
        return "El Ayuntamiento de Bilbao"
    if source == "DEIA - Bizkaimove":
        return "Bizkaimove"
    return source


def _is_single_specific_request(query_context: QueryUnderstanding) -> bool:
    return bool(query_context.lugares or query_context.carreteras)


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
