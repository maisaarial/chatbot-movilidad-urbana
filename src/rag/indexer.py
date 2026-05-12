import csv
import hashlib
import re
from pathlib import Path
from typing import Any

from src.config import settings
from src.rag.vector_store import VectorStore

CSV_SPECS = [
    ("incidencia", "incidents.csv"),
    ("camara", "cameras.csv"),
    ("congestion", "congestion.csv"),
    ("corpus_multifuente", "corpus_movilidad.csv"),
]


def build_index(reset: bool = True) -> dict[str, Any]:
    vector_store = VectorStore.from_env()
    if reset:
        vector_store.reset_collection()

    documents, metadatas, ids, stats = load_processed_documents(settings.processed_data_dir)
    if documents:
        vector_store.add_documents(documents=documents, metadatas=metadatas, ids=ids)

    return {
        "documents_indexed": len(documents),
        "document_type_counts": stats["document_type_counts"],
        "source_counts": stats["source_counts"],
        "persist_dir": str(settings.chroma_persist_dir),
        "collection": settings.chroma_collection_name,
    }


def load_processed_documents(
    processed_dir: Path,
) -> tuple[list[str], list[dict[str, Any]], list[str], dict[str, dict[str, int]]]:
    documents = []
    metadatas = []
    ids = []
    stats: dict[str, dict[str, int]] = {
        "document_type_counts": {},
        "source_counts": {},
    }

    for doc_type, filename in CSV_SPECS:
        path = processed_dir / filename
        if not path.exists():
            continue

        with path.open("r", encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            for row_number, row in enumerate(reader, start=1):
                text = _row_to_text(row, doc_type)
                if not text:
                    continue

                metadata = _row_to_metadata(row, doc_type, filename, row_number)
                documents.append(text)
                metadatas.append(metadata)
                ids.append(_stable_id(doc_type, filename, row_number, text))
                _increment(stats["document_type_counts"], doc_type)
                _increment(stats["source_counts"], _source_for_count(metadata, doc_type))

    return documents, metadatas, ids, stats


def _row_to_text(row: dict[str, str], doc_type: str) -> str:
    rag_text = (row.get("rag_text") or "").strip()
    if rag_text:
        return rag_text

    if doc_type == "corpus_multifuente":
        pieces = [
            (row.get("title") or "").strip(),
            (row.get("text") or "").strip(),
        ]
        return ". ".join(piece for piece in pieces if piece)

    pieces = []
    for key, value in row.items():
        clean_value = (value or "").strip()
        if clean_value:
            pieces.append(f"{key}: {clean_value}")
    return ". ".join(pieces)


def _row_to_metadata(
    row: dict[str, str],
    doc_type: str,
    filename: str,
    row_number: int,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "document_type": doc_type,
        "tipo": doc_type,
        "source_file": filename,
        "row_number": row_number,
    }
    source = _first_non_empty(row.get("source"), row.get("fuente"), _default_source(doc_type))
    if source:
        metadata["source"] = source
    if doc_type == "corpus_multifuente":
        tipo_evento = (row.get("tipo_evento") or "").strip()
        if tipo_evento:
            metadata["tipo"] = tipo_evento
        author = _extract_rag_field(row.get("rag_text", ""), "Autor")
        language = _extract_rag_field(row.get("rag_text", ""), "Idioma")
        if author and author != "no disponible":
            metadata["author"] = author
            metadata["author_handle"] = author
        if language and language != "no disponible":
            metadata["language"] = language

    for field, raw_value in row.items():
        if field == "rag_text":
            continue
        value = (raw_value or "").strip()
        if value:
            metadata[field] = value

    return metadata


def _default_source(doc_type: str) -> str:
    if doc_type in {"incidencia", "camara"}:
        return "Trafikoa"
    if doc_type == "congestion":
        return "Ayuntamiento Bilbao"
    return doc_type


def _source_for_count(metadata: dict[str, Any], doc_type: str) -> str:
    return str(
        metadata.get("source")
        or metadata.get("fuente")
        or _default_source(doc_type)
        or doc_type
    )


def _increment(counts: dict[str, int], key: str) -> None:
    counts[key] = counts.get(key, 0) + 1


def _first_non_empty(*values: Any) -> str:
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _extract_rag_field(rag_text: str, field: str) -> str:
    pattern = rf"(?:^|\.\s*){re.escape(field)}:\s*(.*?)(?=\.\s*[A-ZÁÉÍÓÚÑ][^.:]{{1,40}}:\s*|$)"
    match = re.search(pattern, rag_text, flags=re.DOTALL)
    if not match:
        return ""
    return match.group(1).strip().strip(".")


def _stable_id(doc_type: str, filename: str, row_number: int, text: str) -> str:
    digest = hashlib.sha256(f"{doc_type}|{filename}|{row_number}|{text}".encode("utf-8")).hexdigest()
    return digest[:32]
