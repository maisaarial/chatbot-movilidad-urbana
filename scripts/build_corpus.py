import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import settings
from src.sources.base import deduplicate_documents, save_corpus_csv, save_raw_json, summarize_by_source
from src.sources.bilbao import fetch_bilbao_documents


def build_corpus() -> dict[str, object]:
    bilbao_documents, bilbao_raw = fetch_bilbao_documents()
    save_raw_json(bilbao_raw, settings.raw_data_dir / "bilbao_raw.json")

    documents = deduplicate_documents(bilbao_documents)
    save_corpus_csv(documents, settings.processed_data_dir / "corpus_movilidad.csv")

    return {
        "total": len(documents),
        "by_source": summarize_by_source(documents),
        "raw_path": str(settings.raw_data_dir / "bilbao_raw.json"),
        "processed_path": str(settings.processed_data_dir / "corpus_movilidad.csv"),
    }


def main() -> None:
    result = build_corpus()
    print(
        "Corpus multifuente construido: "
        f"total={result['total']}, "
        f"by_source={result['by_source']}, "
        f"processed_path={result['processed_path']}"
    )


if __name__ == "__main__":
    main()
