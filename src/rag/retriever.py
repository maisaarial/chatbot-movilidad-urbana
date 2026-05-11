import re
import unicodedata
from typing import Any

from src.config import settings
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
    "un",
    "una",
    "unas",
    "unos",
}

GENERIC_DOMAIN_TERMS = {
    "camara",
    "camaras",
    "congestion",
    "incidencia",
    "incidencias",
    "trafico",
}


def retrieve(query: str, k: int = 5) -> list[dict[str, Any]]:
    if not query.strip():
        return []

    vector_store = VectorStore.from_env()
    vector_results = vector_store.search(query=query, limit=max(k * 4, k))
    exact_results = _exact_matches(vector_store, query, limit=k)

    merged_results = []
    seen_texts = set()
    for result in exact_results + vector_results:
        document = result.get("document", "")
        if not document or document in seen_texts:
            continue
        seen_texts.add(document)
        merged_results.append(result)
        if len(merged_results) >= k:
            break

    return [
        {
            "text": result.get("document", ""),
            "distance": result.get("distance"),
            "score": _distance_to_score(result.get("distance")),
            "metadata": result.get("metadata", {}),
        }
        for result in merged_results
    ]


def retrieve_from_settings(query: str) -> list[dict[str, Any]]:
    return retrieve(query=query, k=settings.rag_top_k)


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
) -> list[dict[str, Any]]:
    terms = _important_terms(query)
    if not terms:
        return []

    road_terms = _road_terms(query)
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
        if road_terms:
            matched_terms = [term for term in road_terms if term in haystack]
        else:
            matched_terms = [term for term in terms if term in haystack]

        if matched_terms:
            matches.append(
                (
                    len(matched_terms),
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


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower())
    return "".join(char for char in normalized if not unicodedata.combining(char))
