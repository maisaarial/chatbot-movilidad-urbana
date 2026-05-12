import html
import re
import unicodedata
from typing import Any
from urllib.parse import quote

import requests

from src.config import settings
from src.sources.base import CorpusDocument, make_document_id

BLUESKY_SOURCE = "Bluesky"
BLUESKY_SOURCE_TYPE = "social_media"
BLUESKY_PUBLIC_BASE_URL = "https://public.api.bsky.app"
BLUESKY_AUTH_BASE_URL = "https://bsky.social"

SEARCH_TERMS = [
    "trafico",
    "tráfico",
    "movilidad",
    "accidente",
    "A-8",
    "AP-8",
    "Bizkaia",
    "Bilbao",
    "Euskadi",
    "retenciones",
    "corte",
    "carretera",
]

MOBILITY_TERMS = [
    "tráfico",
    "trafico",
    "movilidad",
    "accidente",
    "retenciones",
    "corte",
    "cortes",
    "carretera",
    "obras",
    "carril",
    "circulación",
    "circulacion",
    "transporte",
    "incidencia",
    "incidencias",
    "A-8",
    "AP-8",
    "BI-637",
    "N-634",
    "trafikoa",
    "zirkulazioa",
    "istripua",
    "auto-ilarak",
    "errepidea",
    "errepideak",
    "mozketa",
    "mozketak",
    "lanak",
    "obrak",
    "garraioa",
    "bidea",
    "errei",
    "errepide mozketa",
]

LOCAL_CONTEXT_TERMS = [
    "euskadi",
    "bizkaia",
    "bilbao",
    "barakaldo",
    "basauri",
    "getxo",
    "galdakao",
    "durango",
    "donostia",
    "gipuzkoa",
    "araba",
    "alava",
    "vitoria-gasteiz",
    "a-8",
    "ap-8",
    "bi-",
    "bi-637",
    "n-634",
]

EVENT_KEYWORDS = {
    "accidente": ["accidente", "accidentes", "siniestro", "istripua"],
    "corte_trafico": [
        "corte",
        "cortes",
        "cortada",
        "trafico",
        "tráfico",
        "trafikoa",
        "circulacion",
        "circulación",
        "zirkulazioa",
        "mozketa",
        "mozketak",
        "errepide mozketa",
    ],
    "obras": ["obra", "obras", "lanak", "obrak"],
    "transporte": [
        "transporte",
        "metro",
        "tranvia",
        "tranvía",
        "autobus",
        "autobús",
        "bizkaibus",
        "bilbobus",
        "euskotren",
        "renfe",
        "garraioa",
    ],
    "incidencia": [
        "incidencia",
        "incidencias",
        "retencion",
        "retención",
        "retenciones",
        "auto-ilarak",
        "averia",
        "avería",
    ],
}

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 chatbot-movilidad-urbana/0.1",
    "Accept": "application/json",
}

ROAD_PATTERN = re.compile(r"\b(?:AP|A|BI|N|GI)-\s*\d+[A-Z]?\b", re.IGNORECASE)

PROVINCES = {
    "bizkaia": "Bizkaia",
    "gipuzkoa": "Gipuzkoa",
    "guipuzcoa": "Gipuzkoa",
    "araba": "Araba",
    "alava": "Araba",
}

MUNICIPALITIES = [
    "Bilbao",
    "Barakaldo",
    "Basauri",
    "Getxo",
    "Leioa",
    "Sestao",
    "Portugalete",
    "Santurtzi",
    "Galdakao",
    "Durango",
    "Gernika",
    "Donostia",
    "Vitoria-Gasteiz",
]


class BlueskySourceError(RuntimeError):
    pass


def fetch_bluesky_documents(
    search_terms: list[str] | None = None,
    limit_per_term: int = 10,
    timeline_limit: int = 150,
    use_search_fallback: bool = True,
) -> tuple[list[CorpusDocument], dict[str, Any]]:
    terms = search_terms or SEARCH_TERMS
    raw_payload: dict[str, Any] = {
        "source": BLUESKY_SOURCE,
        "source_type": BLUESKY_SOURCE_TYPE,
        "api": "app.bsky.feed.getTimeline",
        "search_terms": terms,
        "timeline_limit": timeline_limit,
        "posts_read_timeline": 0,
        "posts_filtered_relevant": 0,
        "posts_discarded": 0,
        "fallback_used": False,
        "items_found": 0,
        "mobility_items": 0,
        "queries": [],
        "errors": [],
        "items": [],
    }

    token = _create_session_token(raw_payload)
    headers = dict(REQUEST_HEADERS)
    if token:
        headers["Authorization"] = f"Bearer {token}"

    raw_items: list[dict[str, str]] = []
    if token:
        try:
            timeline_items, timeline_raw = _get_timeline_posts(
                base_url=BLUESKY_AUTH_BASE_URL,
                headers=headers,
                limit=timeline_limit,
            )
            raw_payload["timeline"] = timeline_raw
            raw_payload["posts_read_timeline"] = len(timeline_items)
            raw_items.extend(timeline_items)
        except Exception as exc:
            raw_payload["errors"].append({"timeline": "home", "error": str(exc)})
    else:
        raw_payload["status"] = "auth_required"
        raw_payload["message"] = (
            "Bluesky requiere BLUESKY_HANDLE y BLUESKY_APP_PASSWORD para leer el "
            "timeline de cuentas seguidas."
        )

    if use_search_fallback and not raw_items:
        raw_payload["fallback_used"] = True
        raw_payload["api_fallback"] = "app.bsky.feed.searchPosts"
        raw_items.extend(_run_search_fallback(terms, headers, bool(token), raw_payload, limit_per_term))

    unique_items = _deduplicate_raw_items(raw_items)
    raw_payload["items_found"] = len(raw_items)
    raw_payload["items"] = unique_items

    documents = [
        _raw_item_to_document(item)
        for item in unique_items
        if _is_mobility_related(item.get("text", ""))
    ]
    raw_payload["mobility_items"] = len(documents)
    raw_payload["posts_filtered_relevant"] = len(documents)
    raw_payload["posts_discarded"] = max(0, len(unique_items) - len(documents))

    if "status" not in raw_payload:
        raw_payload["status"] = "ok" if documents else "empty"
        if not documents:
            raw_payload["message"] = (
                "Bluesky respondio, pero no se encontraron posts del timeline que "
                "pasaran el filtro de movilidad en espanol/euskera."
            )

    return documents, raw_payload


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_scalar(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", html.unescape(str(value))).strip()


def build_rag_text(document: CorpusDocument, author: str = "", language: str = "") -> str:
    pieces = [
        f"Fuente: {document.source}",
        f"Tipo de fuente: {document.source_type}",
        f"Fecha: {document.timestamp or 'no disponible'}",
        f"Autor: {author or 'no disponible'}",
        f"Idioma: {language or 'no disponible'}",
        f"Municipio: {document.municipio or 'no disponible'}",
        f"Provincia: {document.provincia or 'no disponible'}",
        f"Carretera: {document.carretera or 'no disponible'}",
        f"Tipo de evento: {document.tipo_evento or 'no disponible'}",
        f"Texto: {document.text}",
        f"URL: {document.url}",
    ]
    return ". ".join(piece for piece in pieces if piece)


def _create_session_token(raw_payload: dict[str, Any]) -> str:
    handle = settings.bluesky_handle.strip()
    password = settings.bluesky_app_password.strip()
    if not handle or not password:
        raw_payload["auth"] = "not_configured"
        return ""

    response = requests.post(
        f"{BLUESKY_AUTH_BASE_URL}/xrpc/com.atproto.server.createSession",
        json={"identifier": handle, "password": password},
        headers=REQUEST_HEADERS,
        timeout=20,
    )
    if response.status_code >= 400:
        raise BlueskySourceError(
            f"No se pudo autenticar en Bluesky: HTTP {response.status_code} {_extract_error(response)}"
        )
    payload = response.json()
    token = str(payload.get("accessJwt") or "")
    raw_payload["auth"] = "configured" if token else "missing_token"
    return token


def _get_timeline_posts(
    base_url: str,
    headers: dict[str, str],
    limit: int,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    target = max(1, min(limit, 150))
    cursor = ""
    items: list[dict[str, str]] = []
    pages: list[dict[str, Any]] = []

    while len(items) < target:
        page_limit = min(100, target - len(items))
        url = f"{base_url}/xrpc/app.bsky.feed.getTimeline?limit={page_limit}"
        if cursor:
            url = f"{url}&cursor={quote(cursor)}"

        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code >= 400:
            if response.status_code in {401, 403}:
                raise BlueskySourceError(
                    "Authentication Required. El timeline de Bluesky requiere sesion valida."
                )
            raise BlueskySourceError(
                f"HTTP {response.status_code} consultando timeline Bluesky: {_extract_error(response)}"
            )

        payload = response.json()
        feed = payload.get("feed") or []
        page_items = [
            _post_to_raw_item(entry.get("post") or {})
            for entry in feed
            if isinstance(entry, dict)
        ]
        page_items = [item for item in page_items if item.get("text")]
        items.extend(page_items)
        pages.append({"status_code": response.status_code, "items_found": len(page_items)})

        cursor = str(payload.get("cursor") or "")
        if not cursor or not feed:
            break

    return items, {"limit": target, "pages": pages, "items_found": len(items)}


def _run_search_fallback(
    terms: list[str],
    headers: dict[str, str],
    has_token: bool,
    raw_payload: dict[str, Any],
    limit_per_term: int,
) -> list[dict[str, str]]:
    base_url = BLUESKY_AUTH_BASE_URL if has_token else BLUESKY_PUBLIC_BASE_URL
    raw_items: list[dict[str, str]] = []
    for term in terms:
        try:
            posts, query_raw = _search_posts(
                term=term,
                base_url=base_url,
                headers=headers,
                limit=limit_per_term,
            )
            raw_payload["queries"].append(query_raw)
            raw_items.extend(posts)
        except BlueskySourceError as exc:
            raw_payload["errors"].append({"term": term, "error": str(exc)})
            if "Authentication Required" in str(exc) or "AuthMissing" in str(exc):
                raw_payload["status"] = "auth_required"
                break
        except Exception as exc:
            raw_payload["errors"].append({"term": term, "error": str(exc)})
    return raw_items


def _search_posts(
    term: str,
    base_url: str,
    headers: dict[str, str],
    limit: int,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    url = (
        f"{base_url}/xrpc/app.bsky.feed.searchPosts"
        f"?q={quote(term)}&limit={max(1, min(limit, 100))}"
    )
    response = requests.get(url, headers=headers, timeout=30)
    if response.status_code >= 400:
        if response.status_code in {401, 403}:
            raise BlueskySourceError(
                "Authentication Required. El endpoint de busqueda de Bluesky no "
                "permite esta consulta sin sesion valida."
            )
        raise BlueskySourceError(
            f"HTTP {response.status_code} consultando Bluesky: {_extract_error(response)}"
        )

    payload = response.json()
    posts = payload.get("posts") or []
    items = [_post_to_raw_item(post) for post in posts]
    items = [item for item in items if item.get("text")]
    return items, {"term": term, "url": url, "status_code": response.status_code, "items_found": len(items)}


def _post_to_raw_item(post: dict[str, Any]) -> dict[str, str]:
    author = post.get("author") or {}
    record = post.get("record") or {}
    uri = str(post.get("uri") or "")
    cid = str(post.get("cid") or "")
    handle = clean_text(author.get("handle"))
    display_name = clean_text(author.get("displayName"))
    language = _extract_language(record, post)
    post_id = _post_id_from_uri(uri)
    post_url = f"https://bsky.app/profile/{handle}/post/{post_id}" if handle and post_id else ""
    text = clean_text(record.get("text"))

    return {
        "id": uri or cid,
        "cid": cid,
        "timestamp": clean_text(record.get("createdAt") or post.get("indexedAt")),
        "text": text,
        "url": post_url,
        "post_url": post_url,
        "author": handle,
        "author_handle": handle,
        "author_display_name": display_name,
        "language": language,
        "raw_text": text,
    }


def _raw_item_to_document(item: dict[str, str]) -> CorpusDocument:
    text = clean_text(item.get("text"))
    raw_text = clean_text(item.get("raw_text") or text)
    url = clean_scalar(item.get("post_url") or item.get("url"))
    author = clean_text(item.get("author_handle") or item.get("author"))
    language = clean_text(item.get("language"))
    title = f"Post de Bluesky de {author}" if author else "Post de Bluesky"

    document = CorpusDocument(
        id=make_document_id(BLUESKY_SOURCE, url or clean_text(item.get("id")), raw_text),
        timestamp=clean_text(item.get("timestamp")),
        source=BLUESKY_SOURCE,
        source_type=BLUESKY_SOURCE_TYPE,
        title=title,
        text=text,
        url=url,
        municipio=_extract_municipality(raw_text),
        provincia=_extract_province(raw_text),
        carretera=_extract_road(raw_text),
        tipo_evento=_classify_event(raw_text),
        raw_text=raw_text,
        rag_text="",
    )
    document.rag_text = build_rag_text(document, author=author, language=language)
    return document


def _extract_language(record: dict[str, Any], post: dict[str, Any]) -> str:
    langs = record.get("langs") or post.get("langs") or []
    if isinstance(langs, list) and langs:
        return clean_text(langs[0])
    if isinstance(langs, str):
        return clean_text(langs)
    return ""


def _deduplicate_raw_items(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen = set()
    unique_items = []
    for item in items:
        key = item.get("id") or item.get("url") or item.get("raw_text")
        if not key or key in seen:
            continue
        seen.add(key)
        unique_items.append(item)
    return unique_items


def _is_mobility_related(text: str) -> bool:
    normalized_text = _normalize(text)
    has_mobility_signal = any(
        _contains_term(normalized_text, term) for term in MOBILITY_TERMS
    )
    has_local_context = any(
        _contains_term(normalized_text, term) for term in LOCAL_CONTEXT_TERMS
    )
    return has_mobility_signal and has_local_context


def _classify_event(text: str) -> str:
    normalized_text = _normalize(text)
    for event_type, keywords in EVENT_KEYWORDS.items():
        if any(_contains_term(normalized_text, keyword) for keyword in keywords):
            return event_type
    return "movilidad"


def _extract_road(text: str) -> str:
    match = ROAD_PATTERN.search(text)
    if not match:
        return ""
    return match.group(0).upper().replace(" ", "")


def _extract_province(text: str) -> str:
    normalized_text = _normalize(text)
    for normalized_province, province in PROVINCES.items():
        if _contains_term(normalized_text, normalized_province):
            return province
    return ""


def _extract_municipality(text: str) -> str:
    normalized_text = _normalize(text)
    for municipality in MUNICIPALITIES:
        if _contains_term(normalized_text, municipality):
            return municipality
    return ""


def _post_id_from_uri(uri: str) -> str:
    if "/" not in uri:
        return ""
    return uri.rsplit("/", 1)[-1]


def _extract_error(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:300]
    return str(payload.get("message") or payload.get("error") or payload)


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", value.lower())
    return "".join(char for char in text if not unicodedata.combining(char))


def _contains_term(normalized_text: str, term: str) -> bool:
    normalized_term = _normalize(term)
    if "-" in normalized_term:
        return normalized_term in normalized_text
    return re.search(rf"\b{re.escape(normalized_term)}\b", normalized_text) is not None
