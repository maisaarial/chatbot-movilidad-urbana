from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from src.config import settings
from src.congestion import CongestionLevel, calcular_congestion
from src.rag.chatbot import answer_question
from src.rag.index_manager import get_index_status, refresh_index, refresh_index_if_stale
from src.rag.ollama_client import OllamaError
from src.rag.vector_store import VectorStore
from src.trafikoa.cameras import get_cameras
from src.trafikoa.camera_search import search_cameras
from src.trafikoa.client import TrafikoaAPIError, TrafikoaClient
from src.trafikoa.congestion import get_congestion_records
from src.trafikoa.incidents import get_current_incidents

app = FastAPI(
    title="Chatbot Movilidad Urbana",
    description="Backend inicial para consultar datos de movilidad y soporte RAG.",
    version="0.1.0",
)

trafikoa_client = TrafikoaClient.from_env()


class ChatRequest(BaseModel):
    question: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/incidencias")
def incidencias() -> dict[str, Any]:
    try:
        data = get_current_incidents(trafikoa_client)
    except TrafikoaAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Error interno procesando incidencias de Trafikoa.",
        ) from exc
    return {"count": len(data), "items": data}


@app.get("/incidents")
def incidents() -> dict[str, Any]:
    return incidencias()


@app.get("/camaras")
def camaras() -> dict[str, Any]:
    try:
        data = get_cameras(trafikoa_client)
    except TrafikoaAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Error interno procesando camaras de Trafikoa.",
        ) from exc
    return {"count": len(data), "items": data}


@app.get("/cameras")
def cameras() -> dict[str, Any]:
    return camaras()


@app.get("/camaras/search")
def camaras_search(
    q: str | None = Query(None, description="Texto libre para buscar camaras."),
    municipio: str | None = Query(None, description="Municipio de la camara."),
    carretera: str | None = Query(None, description="Carretera de la camara."),
    provincia: str | None = Query(None, description="Provincia de la camara."),
    limit: int = Query(10, ge=1, le=100, description="Numero maximo de resultados."),
) -> dict[str, Any]:
    try:
        items = search_cameras(
            q=q,
            municipio=municipio,
            carretera=carretera,
            provincia=provincia,
            limit=limit,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Error interno buscando camaras procesadas.",
        ) from exc
    return {"count": len(items), "items": items}


@app.get("/congestion")
def congestion(
    valor: float | None = Query(
        None,
        ge=0,
        description="Valor puntual para clasificar sin consultar Trafikoa.",
    ),
    umbral_bajo: float = Query(
        settings.congestion_low_threshold,
        ge=0,
        description="Umbral bajo para valor_trafico.",
    ),
    umbral_alto: float = Query(
        settings.congestion_high_threshold,
        ge=0,
        description="Umbral alto para valor_trafico.",
    ),
    max_pages: int | None = Query(
        None,
        ge=1,
        le=500,
        description="Maximo de paginas de flows a descargar.",
    ),
    source_id: int | None = Query(
        settings.trafikoa_congestion_source_id,
        ge=1,
        le=7,
        description="Fuente Trafikoa para flows. Por defecto, Ayuntamiento Bilbao.",
    ),
) -> dict[str, Any]:
    if valor is not None:
        try:
            level = calcular_congestion(
                valor=valor,
                umbral_bajo=umbral_bajo,
                umbral_alto=umbral_alto,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"level": level.value}

    try:
        data = get_congestion_records(
            trafikoa_client,
            umbral_bajo=umbral_bajo,
            umbral_alto=umbral_alto,
            max_pages=max_pages,
            source_id=source_id,
        )
    except TrafikoaAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Error interno procesando congestion de Trafikoa.",
        ) from exc

    return {
        "count": len(data),
        "thresholds": {
            "umbral_bajo": umbral_bajo,
            "umbral_alto": umbral_alto,
            "unidad": "vehiculos/intervalo",
        },
        "items": data,
    }


@app.get("/congestion/demo-speed")
def congestion_demo_speed(
    speed_kmh: float = Query(..., ge=0, description="Velocidad media actual en km/h."),
    free_flow_speed_kmh: float = Query(
        80,
        gt=0,
        description="Velocidad esperada en condiciones fluidas.",
    )
):
    ratio_value = max(free_flow_speed_kmh - speed_kmh, 0)
    level = calcular_congestion(ratio_value, 20, 45)
    return {"level": level.value}


@app.post("/rag/documents")
def add_documents(documents: list[str]) -> dict[str, Any]:
    if not documents:
        raise HTTPException(status_code=400, detail="Debes enviar al menos un documento.")

    ids = VectorStore.from_env().add_documents(documents)
    return {"count": len(ids), "ids": ids}


@app.get("/rag/search")
def rag_search(query: str, limit: int = Query(3, ge=1, le=10)) -> dict[str, Any]:
    try:
        index_status = refresh_index_if_stale()
        results = VectorStore.from_env().search(query=query, limit=limit)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error actualizando o consultando el indice RAG: {exc}",
        ) from exc
    return {"query": query, "index_status": index_status, "results": results}


@app.get("/rag/status")
def rag_status() -> dict[str, Any]:
    return get_index_status()


@app.post("/rag/refresh")
def rag_refresh() -> dict[str, Any]:
    try:
        return refresh_index(reason="manual")
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error reconstruyendo el indice RAG: {exc}",
        ) from exc


@app.post("/chat")
def chat(request: ChatRequest) -> dict[str, Any]:
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="La pregunta no puede estar vacia.")

    try:
        return answer_question(request.question)
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Error interno ejecutando el chatbot RAG.",
        ) from exc


@app.get("/levels")
def levels() -> dict[str, list[str]]:
    return {"levels": [level.value for level in CongestionLevel]}
