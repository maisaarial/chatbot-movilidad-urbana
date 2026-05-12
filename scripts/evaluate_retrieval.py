import argparse
import csv
import sys
import unicodedata
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.rag.retriever import retrieve

DEFAULT_EVAL_PATH = PROJECT_ROOT / "data" / "evaluation" / "eval_queries.csv"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "evaluation" / "retrieval_results.csv"
NONE_VALUES = {"", "none", "n/a", "na", "null", "ninguna", "ninguno"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Evalua retrieval RAG con una muestra anotada.")
    parser.add_argument("--eval-file", default=str(DEFAULT_EVAL_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()

    eval_rows = _read_csv(Path(args.eval_file))
    results = [evaluate_row(row, k=args.k) for row in eval_rows]
    _write_csv(Path(args.output), results)

    metric_rows = [row for row in results if row["metric_applicable"] == "true"]
    hits = sum(1 for row in metric_rows if row["hit_at_k"] == "true")
    reciprocal_sum = sum(float(row["reciprocal_rank"]) for row in metric_rows)
    recall_at_k = hits / len(metric_rows) if metric_rows else 0.0
    mrr = reciprocal_sum / len(metric_rows) if metric_rows else 0.0

    print(f"retrieval_queries={len(results)}")
    print(f"metric_applicable={len(metric_rows)}")
    print(f"recall@{args.k}={recall_at_k:.3f}")
    print(f"mrr@{args.k}={mrr:.3f}")
    print(f"output={args.output}")


def evaluate_row(row: dict[str, str], k: int) -> dict[str, str]:
    question = row.get("question", "")
    expected_source = row.get("expected_source", "")
    expected_source_type = row.get("expected_source_type", "")
    metric_applicable = not _is_none(expected_source) or not _is_none(expected_source_type)

    try:
        retrieved = retrieve(question, k=k)
        error = ""
    except Exception as exc:
        retrieved = []
        error = str(exc)

    source_rank = _first_rank(retrieved, expected_source, field_names=["source", "fuente"])
    type_rank = _first_rank(
        retrieved,
        expected_source_type,
        field_names=["source_type", "document_type", "tipo", "tipo_evento"],
    )
    effective_rank = source_rank or type_rank
    hit_at_k = bool(metric_applicable and effective_rank)
    reciprocal_rank = (1 / effective_rank) if hit_at_k and effective_rank else 0.0

    return {
        "id": row.get("id", ""),
        "question": question,
        "expected_intent": row.get("expected_intent", ""),
        "expected_entities": row.get("expected_entities", ""),
        "expected_source_type": expected_source_type,
        "expected_source": expected_source,
        "top_k": str(k),
        "metric_applicable": str(metric_applicable).lower(),
        "hit_at_k": str(hit_at_k).lower(),
        "source_rank": str(source_rank or ""),
        "source_type_rank": str(type_rank or ""),
        "reciprocal_rank": f"{reciprocal_rank:.4f}",
        "top_sources": _join_top_values(retrieved, "source", fallback="fuente"),
        "top_source_types": _join_top_values(retrieved, "source_type", fallback="document_type"),
        "top_titles": _join_top_values(retrieved, "title"),
        "error": error,
    }


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _first_rank(
    results: list[dict[str, Any]],
    expected: str,
    field_names: list[str],
) -> int | None:
    if _is_none(expected):
        return None
    expected_norm = _normalize(expected)
    for index, result in enumerate(results, start=1):
        metadata = result.get("metadata") or {}
        values = [metadata.get(field) for field in field_names]
        for value in values:
            value_norm = _normalize(str(value or ""))
            if value_norm and (expected_norm == value_norm or expected_norm in value_norm):
                return index
    return None


def _join_top_values(results: list[dict[str, Any]], field: str, fallback: str = "") -> str:
    values = []
    for result in results:
        metadata = result.get("metadata") or {}
        value = metadata.get(field) or (metadata.get(fallback) if fallback else "")
        values.append(str(value or ""))
    return " | ".join(values)


def _is_none(value: str) -> bool:
    return _normalize(value) in NONE_VALUES


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value).strip().lower())
    return "".join(char for char in normalized if not unicodedata.combining(char))


if __name__ == "__main__":
    main()
