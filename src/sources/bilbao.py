import html
import re
import unicodedata
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin

import requests

from src.sources.base import CorpusDocument, make_document_id

BILBAO_AVISOS_URL = (
    "https://www.bilbao.eus/cs/Satellite?"
    "cid=3000075232&language=es&pageid=3000075232&"
    "pagename=Bilbaonet%2FPage%2FBIO_ListadoAvisos"
)
BILBAO_SOURCE = "Ayuntamiento de Bilbao"
BILBAO_SOURCE_TYPE = "web_institucional"

MOBILITY_KEYWORDS = [
    "trafico",
    "corte de trafico",
    "cortes de trafico",
    "circulacion",
    "calzada",
    "carril",
    "carriles",
    "acera",
    "aparcamiento",
    "ocupacion",
    "obra",
    "obras",
    "transporte",
    "autobus",
    "bilbobus",
    "metro",
    "tranvia",
    "peatonal",
    "peatones",
    "ascensor",
    "carretera",
]

EVENT_KEYWORDS = {
    "corte_trafico": ["trafico", "circulacion", "carril", "carriles"],
    "obras": ["obra", "obras", "calzada", "acera", "aparcamiento", "ocupacion"],
    "transporte": ["transporte", "autobus", "bilbobus", "metro", "tranvia"],
}

DATE_PATTERN = re.compile(r"\b\d{1,2} de [a-záéíóúñ]+ de \d{4}\b", re.IGNORECASE)


def fetch_bilbao_documents(url: str = BILBAO_AVISOS_URL) -> tuple[list[CorpusDocument], dict[str, Any]]:
    response = requests.get(
        url,
        timeout=30,
        headers={"User-Agent": "chatbot-movilidad-urbana/0.1"},
    )
    response.raise_for_status()

    html_text = response.text
    parser = BilbaoAvisosParser(base_url=url)
    parser.feed(html_text)
    parser.close()

    raw_items = parser.items
    if not raw_items:
        raise RuntimeError(
            "No se pudieron extraer avisos de la pagina del Ayuntamiento de Bilbao. "
            "La estructura HTML puede haber cambiado o la pagina no devolvio avisos."
        )

    documents = [
        _raw_item_to_document(item)
        for item in raw_items
        if _is_mobility_related(item)
    ]

    raw_payload = {
        "url": url,
        "status_code": response.status_code,
        "items_found": len(raw_items),
        "mobility_items": len(documents),
        "items": raw_items,
    }
    return documents, raw_payload


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def build_rag_text(document: CorpusDocument) -> str:
    pieces = [
        f"Fuente: {document.source}",
        f"Tipo de fuente: {document.source_type}",
        f"Fecha: {document.timestamp or 'no disponible'}",
        f"Municipio: {document.municipio or 'no disponible'}",
        f"Provincia: {document.provincia or 'no disponible'}",
        f"Tipo de evento: {document.tipo_evento or 'no disponible'}",
        f"Titulo: {document.title}",
        f"Texto: {document.text}",
        f"URL: {document.url}",
    ]
    return ". ".join(piece for piece in pieces if piece)


class BilbaoAvisosParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.items: list[dict[str, str]] = []
        self._current_date = ""
        self._pending_date = ""
        self._current_item: dict[str, str] | None = None
        self._current_tag = ""
        self._capture_link = False
        self._capture_summary = False
        self._heading_level = ""
        self._last_heading_closed = False
        self._inside_main_list = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._current_tag = tag
        attrs_dict = dict(attrs)

        if tag in {"h3", "h4"}:
            self._heading_level = tag

        if tag == "a" and self._heading_level == "h4" and self._current_item is None:
            href = attrs_dict.get("href") or ""
            if "autoplay=si" in href:
                return
            self._current_item = {
                "timestamp": self._current_date,
                "title": "",
                "text": "",
                "url": urljoin(self.base_url, href),
            }
            self._capture_link = True

        if tag == "p" and self._last_heading_closed and self._current_item:
            self._capture_summary = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._capture_link:
            self._capture_link = False
        if tag == "p" and self._capture_summary:
            self._capture_summary = False
            self._finish_item()
        if tag in {"h3", "h4"}:
            self._heading_level = ""
            if tag == "h4" and self._current_item:
                self._last_heading_closed = True

    def handle_data(self, data: str) -> None:
        text = clean_text(data)
        if not text:
            return

        date_match = DATE_PATTERN.fullmatch(text)
        if date_match:
            self._current_date = text
            self._inside_main_list = True
            return

        if self._capture_link and self._current_item:
            title = clean_text(f"{self._current_item['title']} {text}")
            if not text.lower().startswith("escuchar "):
                self._current_item["title"] = title
            return

        if self._capture_summary and self._current_item:
            summary = clean_text(f"{self._current_item['text']} {text}")
            self._current_item["text"] = summary

    def _finish_item(self) -> None:
        if not self._current_item:
            return

        title = clean_text(self._current_item.get("title"))
        text = clean_text(self._current_item.get("text"))
        if title and text and self._inside_main_list:
            self.items.append(
                {
                    "timestamp": clean_text(self._current_item.get("timestamp")),
                    "title": title,
                    "text": text,
                    "url": clean_text(self._current_item.get("url")),
                    "raw_text": clean_text(f"{title}. {text}"),
                }
            )

        self._current_item = None
        self._last_heading_closed = False


def _raw_item_to_document(item: dict[str, str]) -> CorpusDocument:
    title = clean_text(item.get("title"))
    text = clean_text(item.get("text"))
    raw_text = clean_text(item.get("raw_text") or f"{title}. {text}")
    url = clean_text(item.get("url"))

    document = CorpusDocument(
        id=make_document_id(BILBAO_SOURCE, url, raw_text),
        timestamp=clean_text(item.get("timestamp")),
        source=BILBAO_SOURCE,
        source_type=BILBAO_SOURCE_TYPE,
        title=title,
        text=text,
        url=url,
        municipio="Bilbao",
        provincia="Bizkaia",
        carretera=_extract_road(raw_text),
        tipo_evento=_classify_event(raw_text),
        raw_text=raw_text,
        rag_text="",
    )
    document.rag_text = build_rag_text(document)
    return document


def _is_mobility_related(item: dict[str, str]) -> bool:
    text = _normalize(f"{item.get('title', '')} {item.get('text', '')}")
    return any(_normalize(keyword) in text for keyword in MOBILITY_KEYWORDS)


def _classify_event(text: str) -> str:
    normalized_text = _normalize(text)
    for event_type, keywords in EVENT_KEYWORDS.items():
        if any(_normalize(keyword) in normalized_text for keyword in keywords):
            return event_type
    return "movilidad"


def _extract_road(text: str) -> str:
    match = re.search(r"\b(?:AP|A|BI|N|GI)-\s*\d+[A-Z]?\b", text, re.IGNORECASE)
    if not match:
        return ""
    return match.group(0).upper().replace(" ", "")


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", value.lower())
    return "".join(char for char in text if not unicodedata.combining(char))
