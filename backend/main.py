from typing import Any

from fastapi import FastAPI, HTTPException, Query

from src.congestion import CongestionLevel, calculate_congestion_level
from src.rag.vector_store import VectorStore
from src.trafikoa.cameras import download_cameras
from src.trafikoa.client import TrafikoaClient
from src.trafikoa.incidents import download_incidents

app = FastAPI(
    title="Chatbot Movilidad Urbana",
    description="Backend inicial para consultar datos de movilidad y soporte RAG.",
    version="0.1.0",
)

trafikoa_client = TrafikoaClient.from_env()
vector_store = VectorStore.from_env()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/incidents")
def incidents() -> dict[str, Any]:
    try:
        data = download_incidents(trafikoa_client)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"count": len(data), "items": data}


@app.get("/cameras")
def cameras() -> dict[str, Any]:
    try:
        data = download_cameras(trafikoa_client)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"count": len(data), "items": data}


@app.get("/congestion")
def congestion(
    speed_kmh: float = Query(..., ge=0, description="Velocidad media actual en km/h."),
    free_flow_speed_kmh: float = Query(
        80,
        gt=0,
        description="Velocidad esperada en condiciones fluidas.",
    ),
    incidents_count: int = Query(0, ge=0, description="Numero de incidencias cercanas."),
) -> dict[str, str]:
    level = calculate_congestion_level(
        speed_kmh=speed_kmh,
        free_flow_speed_kmh=free_flow_speed_kmh,
        incidents_count=incidents_count,
    )
    return {"level": level.value}


@app.post("/rag/documents")
def add_documents(documents: list[str]) -> dict[str, Any]:
    if not documents:
        raise HTTPException(status_code=400, detail="Debes enviar al menos un documento.")

    ids = vector_store.add_documents(documents)
    return {"count": len(ids), "ids": ids}


@app.get("/rag/search")
def rag_search(query: str, limit: int = Query(3, ge=1, le=10)) -> dict[str, Any]:
    results = vector_store.search(query=query, limit=limit)
    return {"query": query, "results": results}


@app.get("/levels")
def levels() -> dict[str, list[str]]:
    return {"levels": [level.value for level in CongestionLevel]}
