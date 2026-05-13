import re
import unicodedata
from typing import Any

from src.config import settings
from src.rag.index_manager import refresh_index_if_stale
from src.rag.query_understanding import (
    INTENT_CAMARAS,
    INTENT_CONGESTION,
    INTENT_CORPUS,
    INTENT_GENERAL,
    INTENT_INCIDENCIAS,
    INTENT_OBRAS_CORTES,
    QueryUnderstanding,
    normalize_for_matching,
    understand_query,
)
from src.rag.vector_store import VectorStore

STOPWORDS = {
    "a",
    "al",
    "de",
    "del",
    "el",
    "en",
    "entre",
    "hay",
    "la",
    "las",
    "lo",
    "los",
    "para",
    "por",
    "que",
    "se",
    "si",
    "sobre",
    "hasta",
    "hacia",
    "un",
    "una",
    "unas",
    "unos",
    "via",
    "vía",
}

GENERIC_DOMAIN_TERMS = {
    "camara",
    "camaras",
    "congestion",
    "incidencia",
    "incidencias",
    "trafico",
}

INTENT_DOCUMENT_TYPES = {
    INTENT_CAMARAS: ["camara"],
    INTENT_CONGESTION: ["congestion"],
    INTENT_INCIDENCIAS: ["incidencia"],
    INTENT_OBRAS_CORTES: ["corpus_multifuente"],
    INTENT_CORPUS: ["corpus_multifuente"],
}

OBRAS_CORTES_SOURCES = ["DEIA - Bizkaimove", "Ayuntamiento de Bilbao"]

ENTITY_FIELDS = [
    "source",
    "fuente",
    "source_type",
    "title",
    "text",
    "raw_text",
    "rag_text",
    "document_type",
    "tipo",
    "tipo_evento",
    "carretera",
    "municipio",
    "provincia",
    "sentido",
    "nombre",
]


def retrieve(
    query: str,
    k: int = 5,
    *,
    query_understanding: QueryUnderstanding | None = None,
    document_type: str | list[str] | None = None,
    source: str | list[str] | None = None,
    carretera: str | list[str] | None = None,
    lugar: str | list[str] | None = None,
) -> list[dict[str, Any]]:
    return retrieve_with_diagnostics(
        query=query,
        k=k,
        query_understanding=query_understanding,
        document_type=document_type,
        source=source,
        carretera=carretera,
        lugar=lugar,
    )["results"]


def retrieve_with_diagnostics(
    query: str,
    k: int = 5,
    *,
    query_understanding: QueryUnderstanding | None = None,
    document_type: str | list[str] | None = None,
    source: str | list[str] | None = None,
    carretera: str | list[str] | None = None,
    lugar: str | list[str] | None = None,
    candidate_k: int = 20,
) -> dict[str, Any]:
    if not query.strip():
        return {
            "results": [],
            "fallback_used": False,
            "strict_result_count": 0,
            "candidate_count": 0,
            "filters": {},
        }

    query_context = query_understanding or understand_query(query)
    filters = _build_filters(
        query_context=query_context,
        document_type=document_type,
        source=source,
        carretera=carretera,
        lugar=lugar,
    )
    refresh_index_if_stale()
    vector_store = VectorStore.from_env()
    candidate_limit = max(candidate_k, k * 4, k)
    vector_results = vector_store.search(query=query, limit=candidate_limit)
    exact_results = _exact_matches(
        vector_store,
        query,
        limit=candidate_limit,
        query_context=query_context,
    )
    candidates = _merge_results(exact_results + vector_results)

    strict_candidates = [
        result for result in candidates if _matches_filters(result, filters)
    ]
    fallback_used = bool(_has_active_filters(filters) and not strict_candidates)
    ranking_pool = strict_candidates if strict_candidates else candidates
    ranked_results = _rerank_results(ranking_pool, query_context)
    ranked_results = _drop_unrequested_cameras(ranked_results, query_context)
    ranked_results = _prefer_entity_matches(ranked_results, query_context)

    return {
        "results": [_format_result(result) for result in ranked_results[:k]],
        "fallback_used": fallback_used,
        "strict_result_count": len(strict_candidates),
        "candidate_count": len(candidates),
        "filters": filters,
    }


def retrieve_from_settings(query: str) -> list[dict[str, Any]]:
    return retrieve(query=query, k=settings.rag_top_k)


def _build_filters(
    query_context: QueryUnderstanding,
    document_type: str | list[str] | None,
    source: str | list[str] | None,
    carretera: str | list[str] | None,
    lugar: str | list[str] | None,
) -> dict[str, list[str]]:
    document_types = _as_list(document_type)
    if not document_types:
        document_types = INTENT_DOCUMENT_TYPES.get(query_context.intent, [])

    sources = _as_list(source)
    if not sources and query_context.source_preference:
        sources = [query_context.source_preference]
    if (
        not sources
        and query_context.intent == INTENT_OBRAS_CORTES
    ):
        sources = OBRAS_CORTES_SOURCES.copy()

    roads = _as_list(carretera) or query_context.carreteras
    places = _as_list(lugar) or query_context.lugares

    return {
        "document_type": document_types,
        "source": sources,
        "carretera": roads,
        "lugar": places,
    }


def _as_list(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [item for item in value if str(item).strip()]


def _has_active_filters(filters: dict[str, list[str]]) -> bool:
    return any(values for values in filters.values())


def _merge_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged_results = []
    seen_keys = set()
    for result in results:
        document = result.get("document", "")
        item_id = result.get("id", "")
        if not document:
            continue
        key = item_id or document
        if key in seen_keys:
            continue
        seen_keys.add(key)
        merged_results.append(result)
    return merged_results


def _format_result(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": result.get("id"),
        "text": result.get("document", ""),
        "distance": result.get("distance"),
        "score": _distance_to_score(result.get("distance")),
        "rerank_score": round(float(result.get("rerank_score", 0.0)), 3),
        "entity_matches": result.get("entity_matches", []),
        "metadata": result.get("metadata", {}),
    }


def _distance_to_score(distance: Any) -> float | None:
    if distance is None:
        return None
    try:
        value = float(distance)
    except (TypeError, ValueError):
        return None
    return 1 / (1 + max(value, 0))


def _exact_matches(
    vector_store: VectorStore,
    query: str,
    limit: int,
    query_context: QueryUnderstanding | None = None,
) -> list[dict[str, Any]]:
    terms = _important_terms(query)
    if query_context is not None:
        for entity in query_context.carreteras + query_context.lugares:
            normalized_entity = _normalize_text(entity)
            if normalized_entity and normalized_entity not in terms:
                terms.append(normalized_entity)
    if not terms:
        return []

    road_terms = _road_terms(query)
    source_terms = _source_terms(query)
    raw = vector_store.collection.get(include=["documents", "metadatas"])
    documents = raw.get("documents") or []
    metadatas = raw.get("metadatas") or []
    ids = raw.get("ids") or []

    matches = []
    for index, document in enumerate(documents):
        metadata = metadatas[index] if index < len(metadatas) else {}
        haystack = _normalize_text(
            " ".join(
                [
                    document or "",
                    " ".join(str(value) for value in metadata.values() if value),
                ]
            )
        )
        source_haystack = _normalize_text(
            " ".join(
                str(metadata.get(field) or "")
                for field in ["source", "source_type", "title", "document_type"]
            )
        )
        if source_terms and not any(term in source_haystack for term in source_terms):
            continue
        if road_terms:
            matched_terms = [term for term in road_terms if term in haystack]
        else:
            matched_terms = [term for term in terms if term in haystack]

        if matched_terms:
            match_weight = len(matched_terms)
            if query_context is not None:
                if query_context.route_to and _normalize_text(query_context.route_to) in haystack:
                    match_weight += 3
                elif query_context.route_from and _normalize_text(query_context.route_from) in haystack:
                    match_weight += 1
            matches.append(
                (
                    match_weight,
                    index,
                    {
                        "id": ids[index] if index < len(ids) else "",
                        "document": document,
                        "distance": 0.0,
                        "metadata": metadata,
                    },
                )
            )

    matches.sort(key=lambda item: (-item[0], item[1]))
    return [match[2] for match in matches[:limit]]


def _important_terms(query: str) -> list[str]:
    road_terms = _road_terms(query)
    raw_terms = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", _normalize_text(query))

    terms = []
    for term in road_terms + raw_terms:
        if term in STOPWORDS or term in GENERIC_DOMAIN_TERMS:
            continue
        if len(term) < 3 and "-" not in term:
            continue
        if term not in terms:
            terms.append(term)
    return terms


def _road_terms(query: str) -> list[str]:
    normalized_query = _normalize_text(query)
    terms = re.findall(r"\b[a-z]{1,3}-\d+[a-z]?\b", normalized_query)
    return list(dict.fromkeys(terms))


def _source_terms(query: str) -> list[str]:
    normalized_query = _normalize_text(query)
    terms = []
    for term in ["bizkaimove", "deia", "bluesky", "ayuntamiento", "trafikoa"]:
        if term in normalized_query:
            terms.append(term)
    return terms


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _matches_filters(
    result: dict[str, Any],
    filters: dict[str, list[str]],
) -> bool:
    metadata = result.get("metadata", {})
    if filters["document_type"]:
        document_type = normalize_for_matching(metadata.get("document_type") or "")
        accepted_types = {normalize_for_matching(value) for value in filters["document_type"]}
        if document_type not in accepted_types:
            return False

    if filters["source"]:
        if not any(_source_matches(value, metadata) for value in filters["source"]):
            return False

    haystack = _result_haystack(result)
    if filters["carretera"] and not all(
        _normalize_road(road) in haystack for road in filters["carretera"]
    ):
        return False

    if filters["lugar"] and not all(
        _place_matches(place, result, haystack) for place in filters["lugar"]
    ):
        return False

    return True


def _rerank_results(
    results: list[dict[str, Any]],
    query_context: QueryUnderstanding,
) -> list[dict[str, Any]]:
    scored_results = []
    for index, result in enumerate(results):
        metadata = result.get("metadata", {})
        haystack = _result_haystack(result)
        score = (_distance_to_score(result.get("distance")) or 0.0) * 10
        entity_matches = _entity_matches(result, query_context, haystack)

        road_matches = [
            road
            for road in query_context.carreteras
            if _normalize_road(road) in haystack
        ]
        place_matches = [
            place
            for place in query_context.lugares
            if _place_matches(place, result, haystack)
        ]
        score += 7 * len(road_matches)
        score += 5 * len(place_matches)

        if query_context.route_to and _place_matches(
            query_context.route_to,
            result,
            haystack,
        ):
            score += 3

        if _intent_matches_document_type(
            query_context.intent,
            metadata.get("document_type"),
        ):
            score += 4

        if query_context.intent == INTENT_OBRAS_CORTES and _is_works_or_closure(metadata):
            score += 2

        if query_context.source_preference and _source_matches(
            query_context.source_preference,
            metadata,
        ):
            score += 3

        if (
            metadata.get("document_type") == "camara"
            and query_context.intent != INTENT_CAMARAS
        ):
            score -= 8

        if _is_bilbao_congestion_for_other_place(metadata, query_context):
            score -= 7

        if _has_query_entities(query_context) and not entity_matches:
            score -= 5

        ranked_result = dict(result)
        ranked_result["rerank_score"] = score
        ranked_result["entity_matches"] = entity_matches
        scored_results.append((score, index, ranked_result))

    scored_results.sort(key=lambda item: (-item[0], item[1]))
    return [item[2] for item in scored_results]


def _drop_unrequested_cameras(
    results: list[dict[str, Any]],
    query_context: QueryUnderstanding,
) -> list[dict[str, Any]]:
    if query_context.intent == INTENT_CAMARAS:
        return results
    non_camera_results = [
        result
        for result in results
        if result.get("metadata", {}).get("document_type") != "camara"
    ]
    return non_camera_results or results


def _prefer_entity_matches(
    results: list[dict[str, Any]],
    query_context: QueryUnderstanding,
) -> list[dict[str, Any]]:
    if not _has_query_entities(query_context):
        return results
    if query_context.is_route and query_context.route_to:
        destination_results = [
            result
            for result in results
            if query_context.route_to in result.get("entity_matches", [])
        ]
        if destination_results:
            return destination_results
    matching_results = [result for result in results if result.get("entity_matches")]
    return matching_results or results


def _entity_matches(
    result: dict[str, Any],
    query_context: QueryUnderstanding,
    haystack: str,
) -> list[str]:
    matches = []
    for road in query_context.carreteras:
        if _normalize_road(road) in haystack:
            matches.append(road)
    for place in query_context.lugares:
        if _place_matches(place, result, haystack):
            matches.append(place)
    if query_context.source_preference and _source_matches(
        query_context.source_preference,
        result.get("metadata", {}),
    ):
        matches.append(query_context.source_preference)
    return list(dict.fromkeys(matches))


def _has_query_entities(query_context: QueryUnderstanding) -> bool:
    return bool(
        query_context.carreteras
        or query_context.lugares
        or query_context.source_preference
    )


def _intent_matches_document_type(intent: str, document_type: Any) -> bool:
    if intent == INTENT_GENERAL:
        return False
    accepted_types = INTENT_DOCUMENT_TYPES.get(intent, [])
    return normalize_for_matching(document_type) in {
        normalize_for_matching(value) for value in accepted_types
    }


def _is_works_or_closure(metadata: dict[str, Any]) -> bool:
    haystack = normalize_for_matching(
        " ".join(
            str(metadata.get(field) or "")
            for field in ["tipo", "tipo_evento", "title", "text"]
        )
    )
    return any(
        term in haystack
        for term in ["obra", "corte", "cortado", "carril", "paso alternativo", "ocupacion"]
    )


def _is_bilbao_congestion_for_other_place(
    metadata: dict[str, Any],
    query_context: QueryUnderstanding,
) -> bool:
    if metadata.get("document_type") != "congestion":
        return False
    if normalize_for_matching(metadata.get("municipio")) != "bilbao":
        return False
    normalized_places = {
        normalize_for_matching(place) for place in query_context.lugares
    }
    return bool(normalized_places and normalized_places != {"bilbao"})


def _source_matches(source_preference: str, metadata: dict[str, Any]) -> bool:
    expected = normalize_for_matching(source_preference)
    source = normalize_for_matching(metadata.get("source") or metadata.get("fuente") or "")
    if expected == "trafikoa":
        document_type = normalize_for_matching(metadata.get("document_type") or "")
        return source in {"trafikoa", "gobierno pais vasco", "ayuntamiento bilbao"} or (
            document_type in {"incidencia", "camara", "congestion"}
            and source != "ayuntamiento de bilbao"
        )
    return bool(expected and source == expected)


def _place_matches(
    place: str,
    result: dict[str, Any],
    haystack: str | None = None,
) -> bool:
    normalized_place = normalize_for_matching(place)
    if not normalized_place:
        return False
    metadata = result.get("metadata", {})
    exact_fields = [
        "municipio",
        "provincia",
        "sentido",
        "title",
        "nombre",
        "carretera",
    ]
    for field in exact_fields:
        field_value = normalize_for_matching(metadata.get(field) or "")
        if field_value and normalized_place and (
            normalized_place == field_value
            or normalized_place in field_value
            or field_value in normalized_place
        ):
            return True
    return normalized_place in (haystack or _result_haystack(result))


def _result_haystack(result: dict[str, Any]) -> str:
    metadata = result.get("metadata", {})
    values = [result.get("document", "")]
    values.extend(str(metadata.get(field) or "") for field in ENTITY_FIELDS)
    values.extend(str(value) for value in metadata.values() if value)
    return normalize_for_matching(" ".join(values))


def _normalize_road(value: Any) -> str:
    return normalize_for_matching(value).replace(" ", "")
