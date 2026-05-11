import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.rag.index_manager import refresh_index


def main() -> None:
    result = refresh_index(reason="script")
    print(
        "RAG index rebuilt: "
        f"{result['documents_indexed']} documents, "
        f"collection={result['collection']}, "
        f"persist_dir={result['persist_dir']}"
    )


if __name__ == "__main__":
    main()
