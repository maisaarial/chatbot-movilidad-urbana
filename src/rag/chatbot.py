import unicodedata
from typing import Any

from src.config import settings
from src.rag.ollama_client import OllamaClient
from src.rag.retriever import retrieve

NO_EVIDENCE_MESSAGE = "No encontré información suficiente en las fuentes disponibles."

SYSTEM_PROMPT = """
Eres un asistente de movilidad urbana. Responde SOLO usando el contexto recuperado.
No uses conocimiento externo, suposiciones ni datos inventados.
Si el contexto no contiene evidencia suficiente para responder, responde exactamente:
No encontré información suficiente en las fuentes disponibles.
Incluye una respuesta breve, clara y en espanol.
"""


def answer_question(question: str, k: int | None = None) -> dict[str, Any]:
    question = question.strip()
    if not question:
        return {"answer": NO_EVIDENCE_MESSAGE, "sources": []}

    results = retrieve(question, k or settings.rag_top_k)
    useful_results = [result for result in results if result.get("text")]
    if not useful_results:
        return {"answer": NO_EVIDENCE_MESSAGE, "sources": []}

    context = _build_context(useful_results)
    prompt = _build_prompt(question, context)
    answer = OllamaClient().generate(prompt=prompt, system=SYSTEM_PROMPT)
    if _is_no_evidence_answer(answer):
        return {"answer": NO_EVIDENCE_MESSAGE, "sources": []}

    return {
        "answer": answer,
        "sources": _sources_from_results(useful_results),
    }


def _build_context(results: list[dict[str, Any]]) -> str:
    blocks = []
    for index, result in enumerate(results, start=1):
        metadata = result.get("metadata", {})
        source = ", ".join(
            str(value)
            for value in [
                metadata.get("tipo"),
                metadata.get("document_type"),
                metadata.get("carretera"),
                metadata.get("municipio"),
                metadata.get("provincia"),
                metadata.get("timestamp"),
                metadata.get("fuente"),
            ]
            if value
        )
        blocks.append(
            f"[Fuente {index}]\n"
            f"Texto: {result.get('text', '')}\n"
            f"Metadatos: {source}\n"
        )
    return "\n".join(blocks)


def _build_prompt(question: str, context: str) -> str:
    return (
        "Contexto recuperado:\n"
        f"{context}\n\n"
        "Pregunta del usuario:\n"
        f"{question}\n\n"
        "Respuesta:"
    )


def _sources_from_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sources = []
    for result in results:
        metadata = result.get("metadata", {})
        sources.append(
            {
                "text": result.get("text"),
                "score": result.get("score"),
                "distance": result.get("distance"),
                "metadata": metadata,
            }
        )
    return sources


def _is_no_evidence_answer(answer: str) -> bool:
    expected = _normalize(NO_EVIDENCE_MESSAGE)
    actual = _normalize(answer)
    return actual.startswith(expected)


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip().lower())
    return "".join(char for char in normalized if not unicodedata.combining(char))
