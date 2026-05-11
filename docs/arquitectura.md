# Arquitectura Del Proyecto

## Vision General

El proyecto `chatbot-movilidad-urbana` esta organizado como una aplicacion Python modular. La solucion separa la interfaz, la API, la conexion con datos externos y la logica de procesamiento.

La idea principal es que cada capa tenga una responsabilidad clara:

- Streamlit presenta la informacion al usuario.
- FastAPI expone endpoints limpios y controlados.
- Los modulos de `src/` consultan Trafikoa, normalizan datos y calculan resultados.
- Los datos originales y procesados se guardan en `data/`.

## Flujo General Del Sistema

```text
Usuario
  |
  v
Frontend Streamlit
  |
  v
Backend FastAPI
  |
  v
src/trafikoa/*
  |
  v
API oficial Trafikoa/Open Data Euskadi
  |
  v
Normalizacion y calculo
  |
  +--> data/raw/*.json
  |
  +--> data/processed/*.csv
  |
  v
Respuesta JSON al backend
  |
  v
Tabla, filtros e imagenes en Streamlit
```

## Frontend Streamlit

El frontend esta en `frontend/app.py`.

Sus responsabilidades son:

- Mostrar una interfaz simple con pestanas.
- Permitir descargar incidencias reales.
- Permitir descargar camaras reales.
- Permitir seleccionar camaras con `image_url` y visualizar la imagen.
- Mostrar registros de congestion.
- Filtrar congestion por carretera y nivel.
- Mostrar resumen de conteo por nivel.
- Probar la busqueda RAG inicial.

Streamlit no consulta directamente Trafikoa. Toda la comunicacion externa se hace a traves del backend FastAPI.

## Backend FastAPI

El backend esta en `backend/main.py`.

Sus responsabilidades son:

- Exponer endpoints HTTP.
- Llamar a los modulos de negocio.
- Devolver errores controlados si falla Trafikoa.
- Mantener una interfaz estable para Streamlit.

Endpoints principales:

| Endpoint | Funcion |
|---|---|
| `/health` | Verifica que el servidor esta activo. |
| `/incidencias` | Devuelve incidencias reales normalizadas. |
| `/camaras` | Devuelve camaras reales normalizadas. |
| `/congestion` | Devuelve registros de congestion calculados con flows reales. |
| `/rag/documents` | Indexa documentos en ChromaDB. |
| `/rag/search` | Busca documentos indexados. |

## Conexion Trafikoa

La conexion con Trafikoa esta centralizada en `src/trafikoa/client.py`.

Este cliente:

- Usa `base_url` desde `src/config.py` o `.env`.
- Tiene una funcion generica `get(endpoint, params=None)`.
- Gestiona timeouts.
- Gestiona errores HTTP.
- Detecta respuestas vacias.
- Guarda respuestas JSON en `data/raw/` cuando corresponde.
- Soporta paginacion con `_page` y `totalPages`.

## Procesamiento

Los modulos de procesamiento estan separados por dominio:

| Modulo | Datos |
|---|---|
| `src/trafikoa/incidents.py` | Incidencias de trafico. |
| `src/trafikoa/cameras.py` | Camaras de trafico. |
| `src/trafikoa/congestion.py` | Flujos y medidores para congestion. |

Cada modulo descarga datos reales, conserva una copia original y genera una version procesada.

## Congestion

La congestion se calcula en dos niveles:

- `src/congestion.py`: contiene la funcion generica `calcular_congestion`.
- `src/trafikoa/congestion.py`: usa flows reales de Trafikoa y aplica la regla de umbrales.

La variable usada actualmente es `totalVehicles`, procedente de los flows de Trafikoa.

## RAG Futuro

El proyecto incluye una primera base RAG en `src/rag/vector_store.py` con ChromaDB. Actualmente permite indexar documentos enviados al endpoint `/rag/documents` y buscarlos con `/rag/search`.

Los registros de congestion ya incluyen el campo `rag_text`, por ejemplo:

```text
Congestion media en medidor:248, Bilbao, Bizkaia. Valor de trafico: 86.0 vehiculos/intervalo. Fecha: 2026-05-11T08:25. Fuente: Ayuntamiento Bilbao.
```

Esto facilita que, en una fase posterior, las incidencias, camaras y congestion puedan convertirse en documentos para consulta semantica.
