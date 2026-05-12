import html
import re
import unicodedata
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin

import requests

from src.sources.base import CorpusDocument, make_document_id

DEIA_TRAFFIC_URL = "https://www.deia.eus/servicios/trafico/"
DEIA_TRAFFIC_RSS_URL = "https://www.deia.eus/rss/section/1056166/"
DEIA_GENERAL_RSS_URL = "https://www.deia.eus/rss/"
DEIA_SECTION_RSS_URLS = [
    "https://www.deia.eus/rss/section/30113",  # Bilbao
    "https://www.deia.eus/rss/section/30112",  # Bizkaia
    "https://www.deia.eus/rss/section/30046",  # Motor
    "https://www.deia.eus/rss/section/30006",  # Sociedad
    "https://www.deia.eus/rss/section/30004",  # Sucesos
]
DEIA_SOURCE = "DEIA"
DEIA_SOURCE_TYPE = "medio_digital"

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 chatbot-movilidad-urbana/0.1",
    "Accept": "application/rss+xml, application/xml, text/xml, text/html;q=0.9, */*;q=0.8",
}

RSS_NAMESPACES = {
    "dc": "http://purl.org/dc/elements/1.1/",
    "atom": "http://www.w3.org/2005/Atom",
    "media": "http://search.yahoo.com/mrss/",
}

MOBILITY_KEYWORDS = [
    "trafico",
    "trafikoa",
    "movilidad",
    "carretera",
    "carreteras",
    "autopista",
    "autovia",
    "circulacion",
    "retencion",
    "retenciones",
    "cortes",
    "obras",
    "calzada",
    "carril",
    "carriles",
    "accidente",
    "accidentes",
    "averia",
    "incidencia",
    "incidencias",
    "atasco",
    "atascos",
    "transporte",
    "metro",
    "tranvia",
    "autobus",
    "bizkaibus",
    "bilbobus",
    "euskotren",
    "renfe",
    "tav",
]

EVENT_KEYWORDS = {
    "accidente": ["accidente", "accidentes", "siniestro"],
    "corte_trafico": ["corte de trafico", "cortes de trafico", "trafico", "circulacion"],
    "obras": ["obras en carretera", "obras de carretera", "calzada", "carril", "carriles"],
    "transporte": [
        "transporte",
        "metro",
        "tranvia",
        "autobus",
        "bizkaibus",
        "bilbobus",
        "euskotren",
        "renfe",
        "tav",
    ],
    "incidencia": ["incidencia", "incidencias", "retencion", "retenciones", "averia"],
}

ROAD_PATTERN = re.compile(r"\b(?:AP|A|BI|N|GI)-\s*\d+[A-Z]?\b", re.IGNORECASE)

PROVINCES = {
    "bizkaia": "Bizkaia",
    "vizcaya": "Bizkaia",
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
    "Amorebieta",
    "Gernika",
    "Vitoria-Gasteiz",
    "Donostia",
    "San Sebastian",
]

STRONG_MOBILITY_TERMS = [
    "trafico",
    "trafikoa",
    "movilidad",
    "carretera",
    "carreteras",
    "autopista",
    "autovia",
    "circulacion",
    "retencion",
    "retenciones",
    "calzada",
    "carril",
    "carriles",
    "accidente",
    "accidentes",
    "averia",
    "incidencia",
    "incidencias",
    "atasco",
    "atascos",
    "transporte",
    "metro",
    "tranvia",
    "autobus",
    "bizkaibus",
    "bilbobus",
    "euskotren",
    "renfe",
    "tav",
]

CONDITIONAL_MOBILITY_TERMS = ["corte", "cortes", "cortar", "cortada", "obra", "obras"]

MOBILITY_SUPPORT_TERMS = [
    *STRONG_MOBILITY_TERMS,
    "vehiculo",
    "vehiculos",
    "patinete",
    "patinetes",
]


class DeiaSourceError(RuntimeError):
    pass


def fetch_deia_documents(
    rss_urls: list[str] | None = None,
    traffic_url: str = DEIA_TRAFFIC_URL,
) -> tuple[list[CorpusDocument], dict[str, Any]]:
    feeds = rss_urls or [
        DEIA_TRAFFIC_RSS_URL,
        *DEIA_SECTION_RSS_URLS,
        DEIA_GENERAL_RSS_URL,
    ]
    raw_payload: dict[str, Any] = {
        "source": DEIA_SOURCE,
        "traffic_url": traffic_url,
        "rss_urls": feeds,
        "items_found": 0,
        "mobility_items": 0,
        "feeds": [],
        "fallback": None,
        "errors": [],
    }

    raw_items: list[dict[str, str]] = []
    for feed_url in feeds:
        try:
            feed_items, feed_raw = _fetch_rss_items(feed_url)
            raw_items.extend(feed_items)
            raw_payload["feeds"].append(feed_raw)
        except Exception as exc:
            raw_payload["errors"].append(
                {"url": feed_url, "error": f"No se pudo consultar RSS DEIA: {exc}"}
            )

    if not raw_items:
        try:
            fallback_items, fallback_raw = _fetch_traffic_page_items(traffic_url)
            raw_items.extend(fallback_items)
            raw_payload["fallback"] = fallback_raw
        except Exception as exc:
            raw_payload["errors"].append(
                {
                    "url": traffic_url,
                    "error": f"No se pudo consultar la pagina de trafico de DEIA: {exc}",
                }
            )

    raw_payload["items_found"] = len(raw_items)
    documents = [
        _raw_item_to_document(item)
        for item in raw_items
        if _is_mobility_related(item)
    ]
    raw_payload["mobility_items"] = len(documents)
    raw_payload["items"] = raw_items

    if not raw_items and raw_payload["errors"]:
        raw_payload["status"] = "error"
        raw_payload["message"] = (
            "DEIA no devolvio noticias procesables. Se conserva el corpus con las "
            "demas fuentes disponibles."
        )
    elif not documents:
        raw_payload["status"] = "empty"
        raw_payload["message"] = (
            "DEIA respondio, pero no se encontraron noticias que pasaran el filtro "
            "de movilidad/trafico."
        )
    else:
        raw_payload["status"] = "ok"

    return documents, raw_payload


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = _strip_html(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def build_rag_text(document: CorpusDocument) -> str:
    pieces = [
        f"Fuente: {document.source}",
        f"Tipo de fuente: {document.source_type}",
        f"Fecha: {document.timestamp or 'no disponible'}",
        f"Municipio: {document.municipio or 'no disponible'}",
        f"Provincia: {document.provincia or 'no disponible'}",
        f"Carretera: {document.carretera or 'no disponible'}",
        f"Tipo de evento: {document.tipo_evento or 'no disponible'}",
        f"Titulo: {document.title}",
        f"Texto: {document.text}",
        f"URL: {document.url}",
    ]
    return ". ".join(piece for piece in pieces if piece)


def _fetch_rss_items(url: str) -> tuple[list[dict[str, str]], dict[str, Any]]:
    response = requests.get(url, headers=REQUEST_HEADERS, timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"

    feed_raw: dict[str, Any] = {
        "url": url,
        "status_code": response.status_code,
        "items_found": 0,
    }
    items = _parse_rss_items(response.text)
    feed_raw["items_found"] = len(items)
    return items, feed_raw


def _parse_rss_items(xml_text: str) -> list[dict[str, str]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise DeiaSourceError(f"RSS XML invalido: {exc}") from exc

    items = []
    for item in root.findall("./channel/item"):
        title = clean_text(_find_text(item, "title"))
        text = clean_text(_find_text(item, "description"))
        url = clean_text(_find_text(item, "link") or _find_text(item, "guid"))
        timestamp = clean_text(_find_text(item, "pubDate"))
        keywords = clean_text(_find_text(item, "media:keywords"))
        creator = clean_text(_find_text(item, "dc:creator"))
        raw_text = clean_text(" ".join(part for part in [title, text, keywords] if part))
        if not title and not text:
            continue
        items.append(
            {
                "timestamp": timestamp,
                "title": title,
                "text": text,
                "url": url,
                "keywords": keywords,
                "creator": creator,
                "raw_text": raw_text,
                "source_feed": "rss",
            }
        )
    return items


def _find_text(element: ET.Element, path: str) -> str:
    if ":" in path:
        namespace, tag = path.split(":", 1)
        child = element.find(f"{namespace}:{tag}", RSS_NAMESPACES)
    else:
        child = element.find(path)
    if child is None or child.text is None:
        return ""
    return child.text


def _fetch_traffic_page_items(url: str) -> tuple[list[dict[str, str]], dict[str, Any]]:
    response = requests.get(url, headers=REQUEST_HEADERS, timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"

    parser = DeiaLinkParser(base_url=url)
    parser.feed(response.text)
    parser.close()

    return parser.items, {
        "url": url,
        "status_code": response.status_code,
        "items_found": len(parser.items),
    }


class DeiaLinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.items: list[dict[str, str]] = []
        self._current_href = ""
        self._current_text = ""
        self._capture_link = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href") or ""
        if not href or "/20" not in href or not href.endswith(".html"):
            return
        self._current_href = urljoin(self.base_url, href)
        self._current_text = ""
        self._capture_link = True

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or not self._capture_link:
            return
        title = clean_text(self._current_text)
        if title:
            self.items.append(
                {
                    "timestamp": "",
                    "title": title,
                    "text": "",
                    "url": self._current_href,
                    "keywords": "",
                    "creator": "",
                    "raw_text": title,
                    "source_feed": "traffic_page",
                }
            )
        self._current_href = ""
        self._current_text = ""
        self._capture_link = False

    def handle_data(self, data: str) -> None:
        if self._capture_link:
            self._current_text = clean_text(f"{self._current_text} {data}")


def _raw_item_to_document(item: dict[str, str]) -> CorpusDocument:
    title = clean_text(item.get("title"))
    text = clean_text(item.get("text"))
    raw_text = clean_text(item.get("raw_text") or f"{title}. {text}")
    url = clean_text(item.get("url"))

    document = CorpusDocument(
        id=make_document_id(DEIA_SOURCE, url, raw_text),
        timestamp=clean_text(item.get("timestamp")),
        source=DEIA_SOURCE,
        source_type=DEIA_SOURCE_TYPE,
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
    document.rag_text = build_rag_text(document)
    return document


def _is_mobility_related(item: dict[str, str]) -> bool:
    text = _normalize(
        " ".join(
            [
                item.get("title", ""),
                item.get("text", ""),
                item.get("keywords", ""),
            ]
        )
    )
    if ROAD_PATTERN.search(text.upper()):
        return True
    if any(_contains_term(text, keyword) for keyword in STRONG_MOBILITY_TERMS):
        return True
    has_conditional_term = any(
        _contains_term(text, keyword) for keyword in CONDITIONAL_MOBILITY_TERMS
    )
    has_support_term = any(_contains_term(text, keyword) for keyword in MOBILITY_SUPPORT_TERMS)
    return has_conditional_term and has_support_term


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
        if normalized_province in normalized_text:
            return province
    return ""


def _extract_municipality(text: str) -> str:
    normalized_text = _normalize(text)
    for municipality in MUNICIPALITIES:
        if _normalize(municipality) in normalized_text:
            return municipality
    return ""


def _strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value)


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", value.lower())
    return "".join(char for char in text if not unicodedata.combining(char))


def _contains_term(normalized_text: str, term: str) -> bool:
    normalized_term = _normalize(term)
    if " " in normalized_term:
        return normalized_term in normalized_text
    return re.search(rf"\b{re.escape(normalized_term)}\b", normalized_text) is not None
