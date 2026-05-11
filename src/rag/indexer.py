import csv
import hashlib
from pathlib import Path
from typing import Any

from src.config import settings
from src.rag.vector_store import VectorStore

CSV_SPECS = [
    ("incidencia", "incidents.csv"),
    ("camara", "cameras.csv"),
    ("congestion", "congestion.csv"),
]


def build_index(reset: bool = True) -> dict[str, Any]:
    vector_store = VectorStore.from_env()
    if reset:
        vector_store.reset_collection()

    documents, metadatas, ids = load_processed_documents(settings.processed_data_dir)
    if documents:
        vector_store.add_documents(documents=documents, metadatas=metadatas, ids=ids)

    return {
        "documents_indexed": len(documents),
        "persist_dir": str(settings.chroma_persist_dir),
        "collection": settings.chroma_collection_name,
    }


def load_processed_documents(processed_dir: Path) -> tuple[list[str], list[dict[str, Any]], list[str]]:
    documents = []
    metadatas = []
    ids = []

    for doc_type, filename in CSV_SPECS:
        path = processed_dir / filename
        if not path.exists():
            continue

        with path.open("r", encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            for row_number, row in enumerate(reader, start=1):
                text = _row_to_text(row)
                if not text:
                    continue

                metadata = _row_to_metadata(row, doc_type, filename, row_number)
                documents.append(text)
                metadatas.append(metadata)
                ids.append(_stable_id(doc_type, filename, row_number, text))

    return documents, metadatas, ids


def _row_to_text(row: dict[str, str]) -> str:
    rag_text = (row.get("rag_text") or "").strip()
    if rag_text:
        return rag_text

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

    for field, raw_value in row.items():
        if field == "rag_text":
            continue
        value = (raw_value or "").strip()
        if value:
            metadata[field] = value

    return metadata


def _stable_id(doc_type: str, filename: str, row_number: int, text: str) -> str:
    digest = hashlib.sha256(f"{doc_type}|{filename}|{row_number}|{text}".encode("utf-8")).hexdigest()
    return digest[:32]
