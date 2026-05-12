import html
import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin

import requests

from src.sources.base import CorpusDocument, make_document_id

DEIA_TRAFFIC_URL = "https://www.deia.eus/servicios/trafico/"
BIZKAIMOVE_IFRAME_URL = "https://www.bizkaimove.eus/bm/inicio.html"
BIZKAIMOVE_INFO_URL = "https://www.bizkaimove.eus/bm/informacion.html"
DEIA_TRAFFIC_RSS_URL = "https://www.deia.eus/rss/section/1056166/"
DEIA_SOURCE = "DEIA - Bizkaimove"
DEIA_SOURCE_TYPE = "trafico_web"

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 chatbot-movilidad-urbana/0.1",
    "Accept": "text/html, application/rss+xml, application/xml;q=0.9, */*;q=0.8",
}

ROAD_PATTERN = re.compile(r"\b(?:AP|A|BI|N|GI)-\s*\d+[A-Z]?\b", re.IGNORECASE)
KM_PATTERN = re.compile(r"\bkm\s+([0-9]+(?:[,.][0-9]+)?)\b", re.IGNORECASE)
SENSE_PATTERN = re.compile(r"\bsentido\s+(.+)$", re.IGNORECASE)

PROVINCES = {
    "bizkaia": "Bizkaia",
    "vizcaya": "Bizkaia",
}

INFORMATIONAL_MESSAGES = [
    "No existen incidencias destacadas.",
    "Todos los puertos de montaña están abiertos.",
]


class DeiaSourceError(RuntimeError):
    pass


def fetch_deia_documents(
    traffic_url: str = DEIA_TRAFFIC_URL,
    info_url: str = BIZKAIMOVE_INFO_URL,
    rss_url: str = DEIA_TRAFFIC_RSS_URL,
) -> tuple[list[CorpusDocument], dict[str, Any]]:
    extracted_at = _now_iso()
    raw_payload: dict[str, Any] = {
        "source": DEIA_SOURCE,
        "source_type": DEIA_SOURCE_TYPE,
        "traffic_url": traffic_url,
        "iframe_url": BIZKAIMOVE_IFRAME_URL,
        "info_url": info_url,
        "rss_fallback_url": rss_url,
        "extracted_at": extracted_at,
        "items_found": 0,
        "mobility_items": 0,
        "informational_messages": [],
        "fallback": None,
        "errors": [],
        "items": [],
    }

    raw_items: list[dict[str, str]] = []
    try:
        page_items, page_raw = _fetch_bizkaimove_info_items(info_url, extracted_at)
        raw_items.extend(page_items)
        raw_payload["bizkaimove_info"] = page_raw
        raw_payload["informational_messages"] = page_raw["informational_messages"]
    except Exception as exc:
        raw_payload["errors"].append(
            {"url": info_url, "error": f"No se pudo extraer Bizkaimove informacion.html: {exc}"}
        )

    if not raw_items:
        try:
            fallback_items, fallback_raw = _fetch_traffic_rss_items(rss_url, extracted_at)
            raw_items.extend(fallback_items)
            raw_payload["fallback"] = fallback_raw
        except Exception as exc:
            raw_payload["errors"].append(
                {"url": rss_url, "error": f"No se pudo consultar RSS de trafico DEIA: {exc}"}
            )

    documents = [_raw_item_to_document(item) for item in raw_items]
    raw_payload["items_found"] = len(raw_items)
    raw_payload["mobility_items"] = len(documents)
    raw_payload["items"] = raw_items

    if documents:
        raw_payload["status"] = "ok"
    elif raw_payload["informational_messages"]:
        raw_payload["status"] = "informational_only"
        raw_payload["message"] = (
            "Bizkaimove respondio, pero solo se encontraron mensajes informativos "
            "sin incidencias/obras convertibles a documentos."
        )
    elif raw_payload["errors"]:
        raw_payload["status"] = "error"
        raw_payload["message"] = (
            "No se pudieron extraer elementos de trafico de DEIA - Bizkaimove. "
            "Se conserva el corpus con las demas fuentes disponibles."
        )
    else:
        raw_payload["status"] = "empty"
        raw_payload["message"] = "No se encontraron elementos de trafico en DEIA - Bizkaimove."

    return documents, raw_payload


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def build_rag_text(document: CorpusDocument) -> str:
    pieces = [
        f"Fuente: {document.source}",
        f"Tipo de fuente: {document.source_type}",
        f"Fecha: {document.timestamp or 'no disponible'}",
        f"Municipio o zona: {document.municipio or 'no disponible'}",
        f"Provincia: {document.provincia or 'no disponible'}",
        f"Carretera: {document.carretera or 'no disponible'}",
        f"Tipo de evento: {document.tipo_evento or 'no disponible'}",
        f"Titulo: {document.title}",
        f"Texto: {document.text}",
        f"URL: {document.url}",
    ]
    return ". ".join(piece for piece in pieces if piece)


def _fetch_bizkaimove_info_items(
    url: str,
    extracted_at: str,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    response = requests.get(url, headers=REQUEST_HEADERS, timeout=30)
    response.raise_for_status()

    parser = BizkaimoveInfoParser(base_url=url, extracted_at=extracted_at)
    parser.feed(response.text)
    parser.close()

    return parser.items, {
        "url": url,
        "status_code": response.status_code,
        "items_found": len(parser.items),
        "informational_messages": parser.informational_messages,
    }


class BizkaimoveInfoParser(HTMLParser):
    def __init__(self, base_url: str, extracted_at: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.extracted_at = extracted_at
        self.items: list[dict[str, str]] = []
        self.informational_messages: list[str] = []
        self._section = ""
        self._current_item: dict[str, str] | None = None
        self._capture_field = ""
        self._capture_link = False
        self._link_text = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        classes = set((attrs_dict.get("class") or "").split())

        if tag == "div":
            if "container-obras" in classes:
                self._section = "obras"
            return

        if tag == "p" and "titulo-obra" in classes:
            self._finish_item()
            self._current_item = {
                "timestamp": self.extracted_at,
                "section": self._section or "obras",
                "title": "",
                "text": "",
                "url": "",
            }
            self._capture_field = "title"
            return

        if tag == "p" and "incidencia-desc" in classes:
            self._capture_field = "text"
            return

        if tag == "a" and self._current_item is not None and self._capture_field == "text":
            href = attrs_dict.get("href") or ""
            self._current_item["url"] = urljoin(self.base_url, href) if href else ""
            self._capture_link = True
            self._link_text = ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "p":
            self._capture_field = ""
            self._capture_link = False
        if tag == "a" and self._capture_link:
            self._capture_link = False

    def handle_data(self, data: str) -> None:
        text = clean_text(data)
        if not text:
            return

        if text in INFORMATIONAL_MESSAGES and text not in self.informational_messages:
            self.informational_messages.append(text)

        if self._current_item is None or not self._capture_field:
            return

        if self._capture_link:
            self._link_text = clean_text(f"{self._link_text} {text}")
            return

        current = self._current_item.get(self._capture_field, "")
        self._current_item[self._capture_field] = clean_text(f"{current} {text}")

    def close(self) -> None:
        self._finish_item()
        super().close()

    def _finish_item(self) -> None:
        if not self._current_item:
            return
        title = clean_text(self._current_item.get("title"))
        text = clean_text(self._current_item.get("text"))
        if title:
            raw_text = clean_text(f"{title}. {text}")
            self.items.append(
                {
                    "timestamp": self._current_item.get("timestamp", ""),
                    "section": self._current_item.get("section", ""),
                    "title": title,
                    "text": text,
                    "url": self._current_item.get("url", ""),
                    "raw_text": raw_text,
                }
            )
        self._current_item = None


def _fetch_traffic_rss_items(url: str, extracted_at: str) -> tuple[list[dict[str, str]], dict[str, Any]]:
    response = requests.get(url, headers=REQUEST_HEADERS, timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"

    try:
        root = ET.fromstring(response.text)
    except ET.ParseError as exc:
        raise DeiaSourceError(f"RSS XML invalido: {exc}") from exc

    items = []
    for item in root.findall("./channel/item"):
        title = clean_text(_find_text(item, "title"))
        text = clean_text(_find_text(item, "description"))
        url_item = clean_text(_find_text(item, "link") or _find_text(item, "guid"))
        raw_text = clean_text(f"{title}. {text}")
        if title or text:
            items.append(
                {
                    "timestamp": clean_text(_find_text(item, "pubDate")) or extracted_at,
                    "section": "rss_fallback",
                    "title": title or "Elemento RSS trafico DEIA",
                    "text": text,
                    "url": url_item,
                    "raw_text": raw_text,
                }
            )

    return items, {"url": url, "status_code": response.status_code, "items_found": len(items)}


def _find_text(element: ET.Element, path: str) -> str:
    child = element.find(path)
    if child is None or child.text is None:
        return ""
    return child.text


def _raw_item_to_document(item: dict[str, str]) -> CorpusDocument:
    title = clean_text(item.get("title"))
    text = clean_text(item.get("text"))
    raw_text = clean_text(item.get("raw_text") or f"{title}. {text}")
    url = clean_text(item.get("url") or BIZKAIMOVE_INFO_URL)

    document = CorpusDocument(
        id=make_document_id(DEIA_SOURCE, f"{url}|{raw_text}", raw_text),
        timestamp=clean_text(item.get("timestamp")) or _now_iso(),
        source=DEIA_SOURCE,
        source_type=DEIA_SOURCE_TYPE,
        title=title,
        text=_build_text(text),
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


def _build_text(text: str) -> str:
    details = _extract_details(text)
    pieces = [text]
    for label, value in details.items():
        if value:
            pieces.append(f"{label}: {value}")
    return clean_text(". ".join(piece for piece in pieces if piece))


def _extract_details(text: str) -> dict[str, str]:
    return {
        "punto_kilometrico": _extract_kilometer(text),
        "sentido": _extract_sense(text),
    }


def _classify_event(text: str) -> str:
    normalized_text = _normalize(text)
    if "paso alternativo" in normalized_text:
        return "paso_alternativo"
    if any(term in normalized_text for term in ["carril", "arcen", "sentido cortado", "carretera cortada"]):
        return "corte_carril"
    if "incidencia" in normalized_text:
        return "incidencia"
    return "obra"


def _extract_road(text: str) -> str:
    match = ROAD_PATTERN.search(text)
    if not match:
        return ""
    return match.group(0).upper().replace(" ", "")


def _extract_kilometer(text: str) -> str:
    match = KM_PATTERN.search(text)
    if not match:
        return ""
    return match.group(1).replace(".", ",")


def _extract_sense(text: str) -> str:
    match = SENSE_PATTERN.search(text)
    if not match:
        return ""
    return clean_text(match.group(1))


def _extract_municipality(text: str) -> str:
    match = re.search(r"\(([^)]+)\)", text)
    if not match:
        return ""
    return clean_text(match.group(1)).title()


def _extract_province(text: str) -> str:
    normalized_text = _normalize(text)
    for normalized_province, province in PROVINCES.items():
        if normalized_province in normalized_text:
            return province
    if _extract_municipality(text):
        return "Bizkaia"
    return ""


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", value.lower())
    return "".join(char for char in text if not unicodedata.combining(char))


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
