# Arquitectura Del Proyecto

## Vision General

El proyecto `chatbot-movilidad-urbana` esta organizado como una aplicacion Python modular. La solucion separa la interfaz, la API, la conexion con datos externos y la logica de procesamiento.

La idea principal es que cada capa tenga una responsabilidad clara:

- Streamlit presenta la informacion al usuario.
- FastAPI expone endpoints limpios y controlados.
- Los modulos de `src/` consultan Trafikoa, normalizan datos y calculan resultados.
- Los modulos de `src/sources/` incorporan fuentes textuales externas en un corpus comun.
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
  +--> src/sources/* --> fuentes externas institucionales
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
- Usar el chatbot RAG local y mostrar las fuentes recuperadas.
- Mostrar el corpus multifuente, filtrar documentos y ejecutar su actualizacion.

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
| `/rag/status` | Devuelve estado, edad y TTL del indice RAG. |
| `/rag/refresh` | Reconstruye manualmente el indice RAG. |
| `/chat` | Responde preguntas con RAG y Ollama local. |
| `/corpus` | Devuelve documentos del corpus multifuente consolidado. |
| `/corpus/refresh` | Reconstruye el corpus multifuente desde fuentes externas. |

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

## Corpus Multifuente

El corpus multifuente se implementa en `src/sources/`.

| Modulo | Responsabilidad |
|---|---|
| `src/sources/base.py` | Define el esquema comun `CorpusDocument`, guardado CSV/JSON y deduplicacion. |
| `src/sources/bilbao.py` | Descarga y normaliza avisos institucionales del Ayuntamiento de Bilbao. |
| `scripts/build_corpus.py` | Ejecuta conectores, guarda datos crudos y genera el CSV consolidado. |

El esquema comun contiene:

```text
id, timestamp, source, source_type, title, text, url, municipio,
provincia, carretera, tipo_evento, raw_text, rag_text
```

La primera fuente externa es la pagina de avisos del Ayuntamiento de Bilbao. Se extraen avisos relacionados con movilidad, trafico, cortes, obras, aparcamiento, calzada y transporte. Si un campo no esta disponible en la fuente, se deja vacio.

El flujo del corpus es:

```text
Ayuntamiento de Bilbao
  -> src/sources/bilbao.py
  -> limpieza HTML y filtro de movilidad
  -> CorpusDocument
  -> deduplicacion por URL o hash de texto
  -> data/raw/bilbao_raw.json
  -> data/processed/corpus_movilidad.csv
  -> GET /corpus y pestana Corpus multifuente
```

En esta fase el corpus multifuente no se indexa todavia en ChromaDB. Solo se prepara `rag_text` para una integracion posterior.

## Congestion

La congestion se calcula en dos niveles:

- `src/congestion.py`: contiene la funcion generica `calcular_congestion`.
- `src/trafikoa/congestion.py`: usa flows reales de Trafikoa y aplica la regla de umbrales.

La variable usada actualmente es `totalVehicles`, procedente de los flows de Trafikoa.

## RAG

El proyecto incluye una base RAG en `src/rag/` con ChromaDB y Ollama local. El indice se reconstruye desde los CSV procesados mediante `scripts/build_rag_index.py`.

El modulo `src/rag/index_manager.py` controla el TTL del indice. Por defecto, `RAG_INDEX_TTL_SECONDS=300`, equivalente a 5 minutos. Antes de consultar el RAG, el sistema comprueba si el indice ha caducado; si esta caducado, lo reconstruye automaticamente desde los CSV procesados.

Los registros de congestion ya incluyen el campo `rag_text`, por ejemplo:

```text
Congestion media en medidor:248, Bilbao, Bizkaia. Valor de trafico: 86.0 vehiculos/intervalo. Fecha: 2026-05-11T08:25. Fuente: Ayuntamiento Bilbao.
```

Esto permite que incidencias, camaras y congestion se consulten como documentos recuperables por el chatbot.

El endpoint `/chat` usa el flujo:

```text
Pregunta del usuario
  -> retrieve(query, k)
  -> contexto recuperado desde ChromaDB
  -> prompt estricto
  -> Ollama local
  -> respuesta + fuentes
```

El RAG sigue usando los CSV de Trafikoa ya consolidados (`incidents.csv`, `cameras.csv` y `congestion.csv`). El nuevo `corpus_movilidad.csv` queda preparado pero fuera del indice hasta que se valide la calidad del dataset multifuente.
