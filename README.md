# Chatbot Movilidad Urbana

Primera version funcional y limpia de un proyecto Python para movilidad urbana en Euskadi. El sistema permite consultar datos reales de la API oficial de Trafikoa/Open Data Euskadi, procesarlos y mostrarlos en una interfaz sencilla.

## Objetivo

El objetivo del proyecto es construir una base tecnica defendible para un chatbot de movilidad urbana. En esta fase no se implementan modelos complejos, sino una arquitectura clara que permite:

- Consultar incidencias reales de Trafikoa.
- Consultar camaras reales de trafico.
- Descargar mediciones reales de flujo de trafico.
- Clasificar congestion en baja, media o alta.
- Guardar datos procesados en CSV.
- Preparar textos para una futura indexacion RAG.
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
src/rag/              Vector store basico con ChromaDB
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
| `src/trafikoa/congestion.py` | Descarga flows/meters y genera registros de congestion. |
| `src/congestion.py` | Reglas generales de clasificacion baja/media/alta. |
| `src/rag/vector_store.py` | Vector store inicial con ChromaDB. |

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
| `GET` | `/incidents` | Alias de `/incidencias`. |
| `GET` | `/cameras` | Alias de `/camaras`. |
| `GET` | `/congestion` | Descarga flows reales y calcula congestion. |
| `GET` | `/congestion?valor=151&umbral_bajo=50&umbral_alto=150` | Clasifica un valor puntual con umbrales. |
| `GET` | `/levels` | Lista niveles de congestion internos. |
| `POST` | `/rag/documents` | Indexa documentos de texto en ChromaDB. |
| `GET` | `/rag/search` | Busca documentos indexados. |

## Archivos Generados

| Archivo | Contenido |
|---|---|
| `data/raw/incidents_raw.json` | Respuesta original paginada de incidencias. |
| `data/processed/incidents.csv` | Incidencias normalizadas. |
| `data/raw/cameras_raw.json` | Respuesta original paginada de camaras. |
| `data/processed/cameras.csv` | Camaras normalizadas. |
| `data/raw/congestion_raw.json` | Respuesta original de flows/meters usada para congestion. |
| `data/processed/congestion.csv` | Registros de congestion normalizados y preparados para RAG. |

## Documentacion

- [Arquitectura](docs/arquitectura.md)
- [API Trafikoa](docs/trafikoa_api.md)
- [Calculo de Congestion](docs/congestion.md)
- [Pruebas](docs/pruebas.md)
- [Uso Local](docs/uso_local.md)

## Estado actual del proyecto

El proyecto cuenta con una primera version funcional. El backend y el frontend arrancan correctamente, los endpoints consultan datos reales de Trafikoa/Open Data Euskadi, las incidencias y camaras se normalizan y se guardan en CSV, y la congestion se calcula usando mediciones reales de `flows`.

La clasificacion de congestion es una primera aproximacion por umbrales sobre `totalVehicles`, con unidad `vehiculos/intervalo`. No se usan datos inventados. Cuando Trafikoa no proporciona nombre de carretera para un medidor, se conserva un identificador real de medidor.

El modulo RAG existe como base tecnica con ChromaDB, pero todavia no integra automaticamente todos los registros generados. Los registros de congestion ya incluyen `rag_text` para facilitar esa extension posterior.
