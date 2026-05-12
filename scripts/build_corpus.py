import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import settings
from src.sources.base import deduplicate_documents, save_corpus_csv, save_raw_json, summarize_by_source
from src.sources.bilbao import fetch_bilbao_documents
from src.sources.bluesky import fetch_bluesky_documents
from src.sources.deia import fetch_deia_documents


def build_corpus() -> dict[str, object]:
    documents = []
    errors = []

    bilbao_documents, bilbao_raw = fetch_bilbao_documents()
    save_raw_json(bilbao_raw, settings.raw_data_dir / "bilbao_raw.json")
    documents.extend(bilbao_documents)

    try:
        deia_documents, deia_raw = fetch_deia_documents()
    except Exception as exc:
        deia_documents = []
        deia_raw = {
            "source": "DEIA",
            "status": "error",
            "message": (
                "No se pudo consultar DEIA. Se conserva el corpus con las demas "
                "fuentes disponibles."
            ),
            "error": str(exc),
        }
        errors.append({"source": "DEIA", "error": str(exc)})
    save_raw_json(deia_raw, settings.raw_data_dir / "deia_raw.json")
    documents.extend(deia_documents)

    try:
        bluesky_documents, bluesky_raw = fetch_bluesky_documents()
    except Exception as exc:
        bluesky_documents = []
        bluesky_raw = {
            "source": "Bluesky",
            "source_type": "social_media",
            "status": "error",
            "message": (
                "No se pudo consultar Bluesky. Se conserva el corpus con las demas "
                "fuentes disponibles."
            ),
            "error": str(exc),
        }
        errors.append({"source": "Bluesky", "error": str(exc)})
    save_raw_json(bluesky_raw, settings.raw_data_dir / "bluesky_raw.json")
    documents.extend(bluesky_documents)

    documents = deduplicate_documents(documents)
    save_corpus_csv(documents, settings.processed_data_dir / "corpus_movilidad.csv")

    return {
        "total": len(documents),
        "by_source": summarize_by_source(documents),
        "raw_paths": {
            "bilbao": str(settings.raw_data_dir / "bilbao_raw.json"),
            "deia": str(settings.raw_data_dir / "deia_raw.json"),
            "bluesky": str(settings.raw_data_dir / "bluesky_raw.json"),
        },
        "processed_path": str(settings.processed_data_dir / "corpus_movilidad.csv"),
        "errors": errors,
    }


def main() -> None:
    result = build_corpus()
    print(
        "Corpus multifuente construido: "
        f"total={result['total']}, "
        f"by_source={result['by_source']}, "
        f"errors={result['errors']}, "
        f"processed_path={result['processed_path']}"
    )


if __name__ == "__main__":
    main()
