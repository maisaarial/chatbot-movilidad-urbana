# Chatbot Movilidad Urbana

Primera version funcional y limpia de un proyecto Python para movilidad urbana en Euskadi. El sistema permite consultar datos reales de la API oficial de Trafikoa/Open Data Euskadi, procesarlos y mostrarlos en una interfaz sencilla.

## Objetivo

El objetivo del proyecto es construir una base tecnica defendible para un chatbot de movilidad urbana. En esta fase no se implementan modelos complejos, sino una arquitectura clara que permite:

- Consultar incidencias reales de Trafikoa.
- Consultar camaras reales de trafico.
- Buscar camaras por lenguaje natural, carretera, municipio o provincia.
- Descargar mediciones reales de flujo de trafico.
- Clasificar congestion en baja, media o alta.
- Guardar datos procesados en CSV.
- Indexar textos en ChromaDB para el chatbot RAG.
- Preguntar en lenguaje natural con un chatbot RAG usando Ollama local.
- Exponer la funcionalidad mediante FastAPI y Streamlit.

## Arquitectura General

El proyecto esta dividido en tres capas principales:

| Capa | Tecnologia | Responsabilidad |
|---|---|---|
| Frontend | Streamlit | Interfaz para consultar datos, ver tablas, filtrar congestion y visualizar camaras. |
| Backend | FastAPI | Endpoints HTTP para exponer incidencias, camaras, congestion y busqueda RAG. |
| Logica de negocio | Python en `src/` | Conexion con Trafikoa, normalizacion, calculo de congestion y vector store. |

Flujo general:

```text
Usuario
  -> Streamlit
  -> FastAPI
  -> Modulos src/trafikoa
  -> API Trafikoa/Open Data Euskadi
  -> data/raw y data/processed
  -> Respuesta al frontend
```

## Estructura

```text
backend/              API con FastAPI
frontend/             Interfaz simple con Streamlit
src/                  Logica de negocio
src/trafikoa/         Cliente y descargas desde Trafikoa Euskadi
src/rag/              Indexacion RAG, recuperacion y cliente Ollama
data/raw/             Respuestas originales descargadas
data/processed/       CSV normalizados
docs/                 Documentacion tecnica del proyecto
```

## Modulos Principales

| Modulo | Descripcion |
|---|---|
| `backend/main.py` | Define la API REST con FastAPI. |
| `frontend/app.py` | Define la interfaz Streamlit. |
| `src/config.py` | Centraliza configuracion desde `.env`. |
| `src/trafikoa/client.py` | Cliente HTTP reutilizable para Trafikoa, con errores, logs, paginacion y guardado JSON. |
| `src/trafikoa/incidents.py` | Descarga y normaliza incidencias. |
| `src/trafikoa/cameras.py` | Descarga y normaliza camaras. |
| `src/trafikoa/camera_search.py` | Busca camaras reales en el CSV procesado. |
| `src/trafikoa/congestion.py` | Descarga flows/meters y genera registros de congestion. |
| `src/congestion.py` | Reglas generales de clasificacion baja/media/alta. |
| `src/rag/vector_store.py` | Vector store inicial con ChromaDB. |
| `src/rag/indexer.py` | Construye el indice RAG desde CSV procesados. |
| `src/rag/retriever.py` | Recupera documentos relevantes desde ChromaDB. |
| `src/rag/ollama_client.py` | Cliente HTTP para Ollama local. |
| `src/rag/chatbot.py` | Orquesta retrieve, prompt y respuesta del LLM local. |
| `scripts/build_rag_index.py` | Script para reconstruir el indice RAG. |

## Requisitos

- Python 3.11 o superior
- PowerShell en Windows
- Conexion a internet para consultar Trafikoa

## Instalacion

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edita `.env` si necesitas ajustar la URL, rutas, umbrales o credenciales de Trafikoa.

Para usar el chatbot RAG con LLM local instala Ollama y descarga el modelo:

```powershell
ollama pull qwen2.5:3b
```

El modelo se puede cambiar en `.env`:

```text
OLLAMA_MODEL=qwen2.5:3b
OLLAMA_TIMEOUT=180
RAG_INDEX_TTL_SECONDS=300
```

## Reconstruir Indice RAG

Antes de usar el chatbot, genera el indice de ChromaDB desde los CSV procesados:

```powershell
.venv\Scripts\python scripts\build_rag_index.py
```

El indice se guarda en:

```text
data/vectorstore
```

## Ejecutar Backend

```powershell
.venv\Scripts\python -m uvicorn backend.main:app --reload
```

API disponible en:

```text
http://127.0.0.1:8000
```

Swagger/OpenAPI:

```text
http://127.0.0.1:8000/docs
```

## Ejecutar Frontend

En otra terminal:

```powershell
.venv\Scripts\python -m streamlit run frontend/app.py
```

Interfaz disponible en:

```text
http://127.0.0.1:8501
```

## Endpoints Disponibles

| Metodo | Endpoint | Descripcion |
|---|---|---|
| `GET` | `/health` | Comprueba que el backend esta funcionando. |
| `GET` | `/incidencias` | Devuelve incidencias reales normalizadas. |
| `GET` | `/camaras` | Devuelve camaras reales normalizadas. |
| `GET` | `/camaras/search` | Busca camaras por texto libre, carretera, municipio o provincia. |
| `GET` | `/incidents` | Alias de `/incidencias`. |
| `GET` | `/cameras` | Alias de `/camaras`. |
| `GET` | `/congestion` | Descarga flows reales y calcula congestion. |
| `GET` | `/congestion?valor=151&umbral_bajo=50&umbral_alto=150` | Clasifica un valor puntual con umbrales. |
| `GET` | `/levels` | Lista niveles de congestion internos. |
| `POST` | `/rag/documents` | Indexa documentos de texto en ChromaDB. |
| `GET` | `/rag/search` | Busca documentos indexados. |
| `GET` | `/rag/status` | Devuelve estado, edad y TTL del indice RAG. |
| `POST` | `/rag/refresh` | Reconstruye manualmente el indice RAG. |
| `POST` | `/chat` | Responde preguntas usando RAG y Ollama local. |

## Archivos Generados

| Archivo | Contenido |
|---|---|
| `data/raw/incidents_raw.json` | Respuesta original paginada de incidencias. |
| `data/processed/incidents.csv` | Incidencias normalizadas. |
| `data/raw/cameras_raw.json` | Respuesta original paginada de camaras. |
| `data/processed/cameras.csv` | Camaras normalizadas. |
| `data/raw/congestion_raw.json` | Respuesta original de flows/meters usada para congestion. |
| `data/processed/congestion.csv` | Registros de congestion normalizados y preparados para RAG. |
| `data/vectorstore/` | Indice ChromaDB y estado TTL reconstruidos desde los CSV procesados. |

## Documentacion

- [Arquitectura](docs/arquitectura.md)
- [API Trafikoa](docs/trafikoa_api.md)
- [Calculo de Congestion](docs/congestion.md)
- [RAG y Ollama](docs/rag.md)
- [Pruebas](docs/pruebas.md)
- [Uso Local](docs/uso_local.md)

## Estado actual del proyecto

El proyecto cuenta con una primera version funcional. El backend y el frontend arrancan correctamente, los endpoints consultan datos reales de Trafikoa/Open Data Euskadi, las incidencias y camaras se normalizan y se guardan en CSV, y la congestion se calcula usando mediciones reales de `flows`.

La clasificacion de congestion es una primera aproximacion por umbrales sobre `totalVehicles`, con unidad `vehiculos/intervalo`. No se usan datos inventados. Cuando Trafikoa no proporciona nombre de carretera para un medidor, se conserva un identificador real de medidor.

El modulo RAG ya puede indexar `incidents.csv`, `cameras.csv` y `congestion.csv` en ChromaDB. El indice se refresca automaticamente por TTL cada 5 minutos cuando se consulta el RAG, y tambien puede reconstruirse manualmente con `POST /rag/refresh` o desde Streamlit. Para preguntas explicitas de camaras, el chatbot prioriza la busqueda estructurada en `data/processed/cameras.csv` para no perder URLs, coordenadas ni enlaces a mapa. Si Ollama no esta instalado o el modelo no esta descargado, el backend devuelve un error claro indicando que debe ejecutarse `ollama pull qwen2.5:3b`.
