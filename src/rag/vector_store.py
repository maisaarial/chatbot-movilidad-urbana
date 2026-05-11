import hashlib
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from src.config import settings


class HashEmbeddingFunction:
    """Tiny deterministic embedding function for the initial prototype."""

    def __init__(self, dimensions: int = 64) -> None:
        self.dimensions = dimensions

    def __call__(self, input: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in input]

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = text.lower().split()
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:2], "big") % self.dimensions
            sign = 1.0 if digest[2] % 2 == 0 else -1.0
            vector[index] += sign

        norm = sum(value * value for value in vector) ** 0.5
        if norm == 0:
            return vector
        return [value / norm for value in vector]


@dataclass
class SearchResult:
    id: str
    document: str
    distance: float | None


class VectorStore:
    def __init__(
        self,
        persist_dir: str,
        collection_name: str,
        embedding_function: HashEmbeddingFunction | None = None,
    ) -> None:
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self.embedding_function = embedding_function or HashEmbeddingFunction()
        self._collection = None

    @classmethod
    def from_env(cls) -> "VectorStore":
        return cls(
            persist_dir=str(settings.chroma_persist_dir),
            collection_name=settings.chroma_collection_name,
        )

    @property
    def collection(self) -> Any:
        if self._collection is None:
            try:
                import chromadb
                from chromadb.config import Settings as ChromaSettings
            except ImportError as exc:
                raise RuntimeError(
                    "ChromaDB no esta instalado. Ejecuta `pip install -r requirements.txt`."
                ) from exc

            client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._collection = client.get_or_create_collection(
                name=self.collection_name,
                embedding_function=self.embedding_function,
            )
        return self._collection

    def add_documents(self, documents: list[str]) -> list[str]:
        ids = [str(uuid4()) for _ in documents]
        self.collection.add(ids=ids, documents=documents)
        return ids

    def search(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        if not query.strip():
            return []

        raw_results = self.collection.query(query_texts=[query], n_results=limit)
        ids = (raw_results.get("ids") or [[]])[0]
        documents = (raw_results.get("documents") or [[]])[0]
        distances = (raw_results.get("distances") or [[]])[0]

        results = []
        for index, item_id in enumerate(ids):
            results.append(
                SearchResult(
                    id=item_id,
                    document=documents[index] if index < len(documents) else "",
                    distance=distances[index] if index < len(distances) else None,
                ).__dict__
            )
        return results
