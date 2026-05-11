# Chatbot RAG Con Ollama

## Objetivo

El chatbot RAG permite hacer preguntas en lenguaje natural sobre incidencias, camaras y congestion. El sistema debe responder solo con informacion recuperada desde el indice local.

No se usan APIs pagas. No se usa OpenAI API. El modelo generativo se ejecuta localmente con Ollama.

## Componentes

| Componente | Archivo | Funcion |
|---|---|---|
| Indexador | `src/rag/indexer.py` | Lee CSV procesados y crea documentos para ChromaDB. |
| Script | `scripts/build_rag_index.py` | Reconstruye el indice desde consola. |
| Vector store | `src/rag/vector_store.py` | Gestiona ChromaDB y embeddings locales. |
| Retriever | `src/rag/retriever.py` | Recupera documentos relevantes para una consulta. |
| Cliente Ollama | `src/rag/ollama_client.py` | Llama al endpoint local de Ollama. |
| Chatbot | `src/rag/chatbot.py` | Construye contexto, prompt y respuesta final. |
| Endpoint | `POST /chat` | Expone el chatbot al frontend. |

## Datos Indexados

El indice se construye desde:

```text
data/processed/incidents.csv
data/processed/cameras.csv
data/processed/congestion.csv
```

Reglas:

- Si una fila tiene `rag_text`, se usa esa columna como texto principal.
- Si no tiene `rag_text`, se construye un texto descriptivo con las columnas disponibles.
- Se guardan metadatos para trazabilidad.

Metadatos principales:

| Metadata | Descripcion |
|---|---|
| `document_type` | Tipo de documento: incidencia, camara o congestion. |
| `tipo` | Tipo propio del dato cuando existe. |
| `carretera` | Carretera o medidor asociado. |
| `municipio` | Municipio. |
| `provincia` | Provincia. |
| `timestamp` | Fecha/hora si existe. |
| `fuente` | Fuente del dato. |
| `image_url` | URL de imagen en camaras si existe. |

## Embeddings

La primera version usa embeddings locales deterministas implementados en `HashEmbeddingFunction`. No dependen de servicios externos ni descargan modelos pagos.

Estos embeddings permiten usar ChromaDB como indice vectorial local. Ademas, el retriever combina la busqueda vectorial con coincidencias exactas en texto y metadatos. Esto ayuda en consultas cortas como:

```text
A-8
```

## ChromaDB

ChromaDB guarda el indice en:

```text
data/vectorstore
```

Coleccion por defecto:

```text
movilidad_urbana
```

Configuracion en `.env`:

```text
CHROMA_PERSIST_DIR=data/vectorstore
CHROMA_COLLECTION_NAME=movilidad_urbana
```

## Reconstruir El Indice

Comando:

```powershell
.venv\Scripts\python scripts\build_rag_index.py
```

Resultado esperado:

```text
RAG index rebuilt: 1412 documents, collection=movilidad_urbana, persist_dir=data\vectorstore
```

El numero puede variar si se actualizan los CSV.

## Recuperacion Semantica

El retriever esta en:

```text
src/rag/retriever.py
```

Funcion:

```python
retrieve(query, k=5)
```

Devuelve:

- texto recuperado
- distancia
- score aproximado
- metadata

Ejemplo:

```powershell
.venv\Scripts\python -c "from src.rag.retriever import retrieve; print(retrieve('A-8', k=2))"
```

## Ollama

Endpoint local usado:

```text
http://localhost:11434
```

Modelo recomendado:

```text
qwen2.5:3b
```

Configuracion:

```text
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b
OLLAMA_TIMEOUT=180
```

Instalacion del modelo:

```powershell
ollama pull qwen2.5:3b
```

Si Ollama no esta instalado, el backend devuelve un error claro indicando que no puede conectar.

## Prompt Del Sistema

El prompt obliga al modelo a responder solo con contexto recuperado:

```text
Responde SOLO usando el contexto recuperado.
No uses conocimiento externo, suposiciones ni datos inventados.
Si el contexto no contiene evidencia suficiente, responde:
No encontré información suficiente en las fuentes disponibles.
```

Ademas, el contexto enviado al modelo no contiene solo texto plano. Cada documento recuperado se envia como una fuente numerada:

```text
[Fuente 1]
Tipo de documento: incidencia
Metadata completa: {"carretera": "A-8", "causa": "Salida", ...}
Texto recuperado: id: 363423. timestamp: ...
```

Para datos tabulares suficientemente claros, el chatbot genera una respuesta extractiva directamente desde la metadata recuperada. Esto evita respuestas genericas como "si, hay varias incidencias" y obliga a listar los campos concretos disponibles.

Ejemplo de respuesta para incidencias:

```text
Si. Segun las fuentes recuperadas, se encontraron estas incidencias:
1. Tipo: Accidente
   Carretera: A-8
   Causa: Salida
   Sentido: Irun
   Municipio/provincia: Bilbao / BIZKAIA
   Fecha/hora: 2026-05-11T17:28
```

En el frontend, la pestaña `Chatbot` muestra las fuentes usadas con una etiqueta descriptiva. Para cada fuente se presenta:

- carretera
- tipo
- causa
- sentido
- municipio
- provincia
- timestamp
- texto recuperado
- metadata completa
- enlace o imagen si existe `image_url`

## Endpoint `/chat`

Request:

```json
{
  "question": "Hay congestion en Bilbao?"
}
```

Response:

```json
{
  "answer": "...",
  "sources": [
    {
      "text": "...",
      "score": 1.0,
      "distance": 0.0,
      "metadata": {
        "document_type": "congestion",
        "municipio": "Bilbao"
      }
    }
  ]
}
```

Comando:

```powershell
$body = @{ question = "Hay congestion en Bilbao?" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/chat" -Body $body -ContentType "application/json"
```

## Limitaciones

| Limitacion | Explicacion |
|---|---|
| Depende de Ollama local | Sin Ollama arrancado no hay generacion de respuesta. |
| Modelo configurable | Si `qwen2.5:3b` no esta descargado, hay que ejecutar `ollama pull qwen2.5:3b`. |
| Embeddings iniciales | Son locales y ligeros; no equivalen a modelos semanticos grandes. |
| Calidad condicionada por CSV | El chatbot solo puede responder sobre informacion indexada. |
| No usa conocimiento externo | Si el contexto no contiene evidencia suficiente, debe indicarlo. |

## Como Probar El Chat

1. Generar datos procesados usando endpoints existentes si hace falta.
2. Reconstruir indice:

```powershell
.venv\Scripts\python scripts\build_rag_index.py
```

3. Descargar modelo:

```powershell
ollama pull qwen2.5:3b
```

4. Arrancar backend:

```powershell
.venv\Scripts\python -m uvicorn backend.main:app --reload
```

5. Probar endpoint:

```powershell
$body = @{ question = "Hay incidencias en la A-8?" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/chat" -Body $body -ContentType "application/json"
```
