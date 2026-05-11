# Chatbot Movilidad Urbana

Primera version funcional y limpia de un proyecto Python para movilidad urbana en Euskadi.

## Estructura

```text
backend/              API con FastAPI
frontend/             Interfaz simple con Streamlit
src/                  Logica de negocio
src/trafikoa/         Cliente y descargas desde Trafikoa Euskadi
src/rag/              Vector store basico con ChromaDB
```

## Requisitos

- Python 3.11 o superior

## Instalacion

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edita `.env` si necesitas ajustar la URL, rutas o credenciales de Trafikoa.

## Ejecutar backend

```bash
uvicorn backend.main:app --reload
```

API disponible en `http://localhost:8000`.

Endpoints iniciales:

- `GET /health`
- `GET /incidents`
- `GET /cameras`
- `GET /congestion`
- `POST /rag/documents`
- `GET /rag/search`

## Ejecutar frontend

En otra terminal:

```bash
streamlit run frontend/app.py
```

## Notas

- La integracion con Trafikoa esta preparada para consumir endpoints JSON configurables y paginados.
- El calculo de congestion es una heuristica simple: baja, media o alta segun velocidad e incidencias.
- El modulo RAG usa ChromaDB con embeddings deterministas ligeros. No incluye todavia modelos complejos.
