import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.config import settings

CORPUS_COLUMNS = [
    "id",
    "timestamp",
    "source",
    "source_type",
    "title",
    "text",
    "url",
    "municipio",
    "provincia",
    "carretera",
    "tipo_evento",
    "raw_text",
    "rag_text",
]

CORPUS_PATH = settings.processed_data_dir / "corpus_movilidad.csv"


@dataclass
class CorpusDocument:
    id: str
    timestamp: str
    source: str
    source_type: str
    title: str
    text: str
    url: str
    municipio: str
    provincia: str
    carretera: str
    tipo_evento: str
    raw_text: str
    rag_text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_document_id(source: str, url: str, text: str) -> str:
    base_value = url.strip() or text.strip()
    digest = hashlib.sha256(f"{source}|{base_value}".encode("utf-8")).hexdigest()
    return digest[:32]


def deduplicate_documents(documents: list[CorpusDocument]) -> list[CorpusDocument]:
    seen = set()
    unique_documents = []

    for document in documents:
        text_hash = _hash_text(document.raw_text or document.text)
        key = f"{document.url.strip()}|{text_hash}" if document.url.strip() else text_hash
        if key in seen:
            continue
        seen.add(key)
        unique_documents.append(document)

    return unique_documents


def save_raw_json(payload: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_corpus_csv(documents: list[CorpusDocument], path: Path = CORPUS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CORPUS_COLUMNS)
        writer.writeheader()
        for document in documents:
            writer.writerow(document.to_dict())


def load_corpus_csv(path: Path = CORPUS_PATH) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as csv_file:
        return [row for row in csv.DictReader(csv_file)]


def summarize_by_source(documents: list[CorpusDocument]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for document in documents:
        summary[document.source] = summary.get(document.source, 0) + 1
    return summary


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()
