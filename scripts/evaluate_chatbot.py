import argparse
import csv
import json
import sys
import unicodedata
from pathlib import Path
from typing import Any

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import settings
from src.rag.chatbot import answer_question

DEFAULT_EVAL_PATH = PROJECT_ROOT / "data" / "evaluation" / "eval_queries.csv"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "evaluation" / "chatbot_results.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description="Evalua respuestas del chatbot con checks simples.")
    parser.add_argument("--eval-file", default=str(DEFAULT_EVAL_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument(
        "--mode",
        choices=["direct", "endpoint"],
        default="direct",
        help="direct usa src.rag.chatbot; endpoint usa POST /chat.",
    )
    parser.add_argument("--endpoint", default=f"{settings.backend_url}/chat")
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()

    eval_rows = _read_csv(Path(args.eval_file))
    results = [
        evaluate_row(
            row=row,
            mode=args.mode,
            endpoint=args.endpoint,
            timeout=args.timeout,
        )
        for row in eval_rows
    ]
    _write_csv(Path(args.output), results)

    completed = [row for row in results if not row["error"]]
    passed = [row for row in completed if row["contains_expected"] == "true"]
    source_hits = [row for row in completed if row["expected_source_found"] == "true"]
    print(f"chatbot_queries={len(results)}")
    print(f"completed={len(completed)}")
    print(f"contains_expected_rate={_ratio(len(passed), len(completed)):.3f}")
    print(f"expected_source_rate={_ratio(len(source_hits), len(completed)):.3f}")
    print(f"output={args.output}")


def evaluate_row(
    row: dict[str, str],
    mode: str,
    endpoint: str,
    timeout: int,
) -> dict[str, str]:
    question = row.get("question", "")
    try:
        payload = _ask_chatbot(question, mode=mode, endpoint=endpoint, timeout=timeout)
        answer = str(payload.get("answer") or "")
        sources = payload.get("sources") or []
        error = ""
    except Exception as exc:
        answer = ""
        sources = []
        error = str(exc)

    expected_terms = _split_terms(row.get("expected_answer_contains", ""))
    matched_terms = [term for term in expected_terms if _contains(answer, term)]
    contains_expected = bool(expected_terms) and len(matched_terms) == len(expected_terms)
    expected_source_found = _expected_source_found(sources, row.get("expected_source", ""))

    return {
        "id": row.get("id", ""),
        "question": question,
        "expected_intent": row.get("expected_intent", ""),
        "expected_source_type": row.get("expected_source_type", ""),
        "expected_source": row.get("expected_source", ""),
        "expected_answer_contains": row.get("expected_answer_contains", ""),
        "contains_expected": str(contains_expected).lower(),
        "matched_terms": ";".join(matched_terms),
        "expected_source_found": str(expected_source_found).lower(),
        "answer": answer,
        "sources_used": json.dumps(_summarize_sources(sources), ensure_ascii=False),
        "error": error,
    }


def _ask_chatbot(question: str, mode: str, endpoint: str, timeout: int) -> dict[str, Any]:
    if mode == "endpoint":
        response = requests.post(endpoint, json={"question": question}, timeout=timeout)
        response.raise_for_status()
        return response.json()
    return answer_question(question)


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


def _expected_source_found(sources: list[dict[str, Any]], expected_source: str) -> bool:
    if _normalize(expected_source) in {"", "none", "n/a", "na", "null"}:
        return True
    expected_norm = _normalize(expected_source)
    for source in sources:
        metadata = source.get("metadata") or {}
        source_value = metadata.get("source") or metadata.get("fuente") or ""
        if not source_value and _normalize(str(metadata.get("document_type") or "")) == "camara":
            source_value = "Trafikoa"
        if expected_norm in _normalize(str(source_value)):
            return True
    return False


def _summarize_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary = []
    for source in sources:
        metadata = source.get("metadata") or {}
        summary.append(
            {
                "source": metadata.get("source")
                or metadata.get("fuente")
                or ("Trafikoa" if metadata.get("document_type") == "camara" else ""),
                "source_type": metadata.get("source_type") or metadata.get("document_type") or "",
                "title": metadata.get("title") or metadata.get("nombre") or "",
                "url": metadata.get("url") or metadata.get("source_url") or metadata.get("image_url") or "",
                "tipo_evento": metadata.get("tipo_evento") or metadata.get("tipo") or "",
                "timestamp": metadata.get("timestamp") or "",
            }
        )
    return summary


def _split_terms(value: str) -> list[str]:
    return [term.strip() for term in value.split(";") if term.strip()]


def _contains(answer: str, term: str) -> bool:
    return _normalize(term) in _normalize(answer)


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value).strip().lower())
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    return without_accents.replace("ã©", "e").replace("ã¡", "a").replace("ã­", "i")


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


if __name__ == "__main__":
    main()
