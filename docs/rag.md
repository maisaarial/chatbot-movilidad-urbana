# Chatbot RAG Con Ollama

## Objetivo

El chatbot RAG permite hacer preguntas en lenguaje natural sobre incidencias, camaras, congestion y el corpus multifuente de movilidad. El sistema debe responder solo con informacion recuperada desde el indice local.

No se usan APIs pagas. No se usa OpenAI API. El modelo generativo se ejecuta localmente con Ollama.

## Componentes

| Componente | Archivo | Funcion |
|---|---|---|
| Indexador | `src/rag/indexer.py` | Lee CSV procesados y crea documentos para ChromaDB. |
| Script | `scripts/build_rag_index.py` | Reconstruye el indice desde consola. |
| Vector store | `src/rag/vector_store.py` | Gestiona ChromaDB y embeddings locales. |
| Gestor de indice | `src/rag/index_manager.py` | Controla TTL, estado y refresco automatico del indice. |
| Retriever | `src/rag/retriever.py` | Recupera documentos relevantes para una consulta. |
| Capacidades | `src/rag/capabilities.py` | Responde preguntas sobre que sabe el sistema y que fuentes usa. |
| Buscador de camaras | `src/trafikoa/camera_search.py` | Busca camaras reales con filtros estructurados. |
| Cliente Ollama | `src/rag/ollama_client.py` | Llama al endpoint local de Ollama. |
| Chatbot | `src/rag/chatbot.py` | Construye contexto, prompt y respuesta final. |
| Endpoint | `POST /chat` | Expone el chatbot al frontend. |

## Datos Indexados

El indice se construye desde:

```text
data/processed/incidents.csv
data/processed/cameras.csv
data/processed/congestion.csv
data/processed/corpus_movilidad.csv
```

Reglas:

- Si una fila tiene `rag_text`, se usa esa columna como texto principal.
- Si una fila del corpus multifuente no tiene `rag_text`, se construye texto con `title` + `text`.
- Para los CSV de Trafikoa sin `rag_text`, se construye un texto descriptivo con las columnas disponibles.
- Se guardan metadatos para trazabilidad.

Metadatos principales:

| Metadata | Descripcion |
|---|---|
| `document_type` | Tipo de documento: incidencia, camara, congestion o corpus_multifuente. |
| `tipo` | Tipo propio del dato cuando existe. |
| `source` | Fuente normalizada del documento. |
| `source_type` | Tipo de fuente en el corpus multifuente. |
| `title` | Titulo del aviso, evento web o post cuando existe. |
| `url` | URL original, PDF o post cuando existe. |
| `tipo_evento` | Tipo de evento del corpus multifuente. |
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
RAG_INDEX_TTL_SECONDS=300
```

## TTL Y Refresco Automatico

El indice RAG tiene un TTL configurable. Por defecto es de 300 segundos, es decir, 5 minutos.

```text
RAG_INDEX_TTL_SECONDS=300
```

El refresco es automatico bajo demanda: antes de recuperar documentos en `retrieve()`, el sistema consulta `src/rag/index_manager.py`. Si el indice ha caducado o no existe estado previo, se reconstruye desde los CSV procesados.

El estado se guarda en:

```text
data/vectorstore/rag_status.json
```

Campos principales del estado:

| Campo | Significado |
|---|---|
| `last_refresh_at` | Fecha/hora UTC de la ultima reconstruccion. |
| `ttl_seconds` | Tiempo de vida configurado. |
| `age_seconds` | Edad actual del indice. |
| `expires_at` | Momento en que caduca. |
| `is_stale` | Indica si el indice esta caducado. |
| `documents_indexed` | Numero de documentos indexados. |
| `last_error` | Ultimo error de reconstruccion si existe. |

## Reconstruir El Indice

Comando:

```powershell
.venv\Scripts\python scripts\build_rag_index.py
```

Resultado esperado:

```text
RAG index rebuilt: 1328 documents, collection=movilidad_urbana, persist_dir=data\vectorstore
Document types indexed: {'incidencia': 307, 'camara': 489, 'congestion': 500, 'corpus_multifuente': 32}
Sources indexed: {'Gobierno Pais Vasco': 136, 'Ayuntamiento Bilbao': 630, 'Trafikoa': 489, 'Ayuntamiento de Bilbao': 8, 'DEIA - Bizkaimove': 22, 'Bluesky': 2, ...}
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

El retriever combina busqueda vectorial con coincidencias exactas sobre texto y metadata. Cuando la pregunta menciona una fuente concreta, como `Bizkaimove` o `Bluesky`, prioriza resultados cuya metadata `source`, `source_type` o `title` corresponda a esa fuente. Esto evita que URLs historicas de imagenes de camaras contaminen consultas sobre DEIA - Bizkaimove.

Ejemplo:

```powershell
.venv\Scripts\python -c "from src.rag.retriever import retrieve; print(retrieve('A-8', k=2))"
```

## Query Understanding Y Filtrado

Antes de recuperar documentos, el chatbot interpreta la pregunta con:

```text
src/rag/query_understanding.py
```

La salida incluye:

- `intent`: `camaras`, `incidencias`, `congestion`, `obras_cortes`, `corpus_multifuente` o `general`.
- `lugares`: municipios, calles o zonas mencionadas.
- `carreteras`: extraidas con regex, por ejemplo `A-8`, `AP-8`, `BI-2405`, `BI-637`, `N-634` o `AP-68`.
- `is_route`, `route_from` y `route_to` cuando aparecen patrones como `desde X hasta Y`, `a X desde Y` o `entre X y Y`.
- `source_preference` cuando se menciona `Trafikoa`, `Ayuntamiento`, `DEIA`, `Bizkaimove` o `Bluesky`.

El retriever usa esa interpretacion para construir filtros preferentes:

| Intent | Prioridad antes del reranking |
|---|---|
| `camaras` | No usa RAG primero; mantiene la busqueda estructurada de camaras. |
| `congestion` | Prioriza `document_type=congestion`. |
| `incidencias` | Prioriza `document_type=incidencia`. |
| `obras_cortes` | Prioriza `document_type=corpus_multifuente` y fuentes `DEIA - Bizkaimove` o `Ayuntamiento de Bilbao`. |
| `corpus_multifuente` | Prioriza documentos del corpus multifuente. |

El retrieval aumenta los candidatos iniciales a 20 como minimo y despues aplica reranking local. Suma puntuacion cuando coinciden carretera, lugar, intent/document_type o fuente preferida. Resta puntuacion a camaras si la pregunta no pide camaras, a congestion de Bilbao cuando se pregunta por otra ubicacion y a documentos que no contienen ninguna entidad detectada.

Si no hay coincidencias con filtros estrictos, se usa fallback semantico. En ese caso la respuesta avisa que no hay coincidencia exacta y solo muestra informacion relacionada.

## Autodescripcion Del Sistema

Antes de ejecutar el RAG normal, el chatbot detecta preguntas de capacidades o introspeccion con reglas simples en:

```text
src/rag/capabilities.py
```

Ejemplos:

```text
Que sabes?
Sobre que te puedo preguntar?
Que fuentes de informacion tienes?
De donde sale la informacion?
Que datos usas?
Puedes calcular rutas?
```

Estas preguntas se responden directamente, sin retrieval semantico y sin llamar a Ollama. La respuesta describe las fuentes reales del sistema:

- Trafikoa: incidencias, camaras y datos de congestion basados en `flows`/`meters`.
- Ayuntamiento de Bilbao: avisos institucionales de movilidad, cortes, obras y ocupaciones.
- DEIA - Bizkaimove: informacion avanzada de trafico, obras, cortes y pasos alternativos.
- Bluesky: publicaciones de cuentas seguidas relacionadas con movilidad/trafico, solo si hay credenciales y posts relevantes.
- ChromaDB/RAG: indice semantico local sobre documentos procesados.
- Ollama/Qwen: generacion local sin APIs pagas.

La respuesta consulta `src/rag/index_manager.py` para incorporar, si esta disponible, el numero de documentos indexados, tipos de documentos y fecha de ultima actualizacion. Tambien explica limitaciones: no calcula rutas completas, no hace predicciones oficiales y solo responde con fuentes disponibles.

## Busqueda Estructurada De Camaras

Las camaras siguen indexadas en ChromaDB, pero cuando la pregunta del usuario es claramente sobre camaras se prioriza una busqueda estructurada sobre `data/processed/cameras.csv`.

Motivo:

- Las camaras tienen campos exactos como `image_url`, `latitude`, `longitude` y `maps_url`.
- El RAG semantico puede recuperar texto relevante, pero no garantiza preservar URLs y coordenadas con precision.
- La busqueda estructurada devuelve datos reales del CSV, listos para mostrar imagenes y enlaces.
- Para preguntas de camaras, el chatbot consulta primero con `only_with_image=true`; si no hay resultados con imagen, busca de nuevo sin ese filtro e indica que la camara existe pero no tiene imagen disponible en la API.

Consultas detectadas como camaras:

```text
Muestrame camaras en Bilbao
Que camaras hay en la A-8
Ver camaras cerca de Galdakao
Camaras en Bizkaia
Hay camara en la BI-637
```

Flujo:

```text
Pregunta del usuario
  -> detectar intencion de camaras
  -> extraer carretera/provincia/texto libre
  -> search_cameras(...)
  -> respuesta estructurada + sources con metadata completa
```

Respuesta esperada:

```text
Si. Encontre estas camaras:
1. Nombre: Iurreta
   Carretera: A-8
   Municipio/provincia: no disponible / no disponible
   Imagen: https://...
   Mapa: https://www.google.com/maps?q=...
```

Si no hay resultados:

```text
No encontre camaras para ese lugar o carretera en las fuentes disponibles.
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

Para datos tabulares y documentos multifuente suficientemente claros, el chatbot genera una respuesta redactada en lenguaje natural a partir de la metadata recuperada. La respuesta principal resume que ocurre, donde ocurre, carretera o calle, sentido, municipio y fecha cuando esos campos existen y aportan valor.

La respuesta principal no copia la metadata completa ni repite etiquetas internas como `document_type`, `source_type` o `Documento multifuente`. Esa trazabilidad queda separada en `Fuentes usadas`.

Ejemplos de respuesta:

```text
Sí. El Ayuntamiento de Bilbao informa de un corte de dos carriles en Alameda Recalde, en sentido Plaza Moyúa. El aviso está fechado el 11 de mayo de 2026.

Bizkaimove recoge varias afecciones de obra o cortes. Entre ellas: un carril cortado en Sondika en la BI-30, un paso alternativo en Mallabia en la N-634 y un sentido cortado en Bilbao en la BI-636.

Sí. En la BI-2405 se encontraron varias incidencias: registros de puerto de montaña sin causa detallada y un accidente por alcance en sentido Lekeitio, en Amoroto.
```

En el frontend, la pestaña `Chatbot` muestra las fuentes usadas con una etiqueta descriptiva. Para cada fuente se presenta:

- source
- source_type
- title
- url, como enlace clicable cuando existe
- tipo_evento
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

Ademas, la respuesta del endpoint incluye `query_understanding` y un resumen de `retrieval`. Streamlit lo muestra en el desplegable `Depuración de consulta` para revisar intent, lugares, carreteras, fuente priorizada, filtros y si se uso fallback semantico.

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
  "query_understanding": {
    "intent": "congestion",
    "lugares": ["Bilbao"],
    "carreteras": [],
    "is_route": false,
    "source_preference": null
  },
  "retrieval": {
    "fallback_used": false,
    "strict_result_count": 5,
    "candidate_count": 20
  },
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

## Endpoints De Gestion RAG

### `GET /rag/status`

Devuelve el estado actual del indice, incluyendo TTL, edad, fecha de caducidad y numero de documentos.

Comando:

```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/rag/status"
```

### `POST /rag/refresh`

Reconstruye manualmente el indice desde:

```text
data/processed/incidents.csv
data/processed/cameras.csv
data/processed/congestion.csv
data/processed/corpus_movilidad.csv
```

Comando:

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/rag/refresh"
```

Streamlit incluye un boton `Actualizar indice RAG ahora` en la pestana `RAG`. Ese boton llama a `POST /rag/refresh` y muestra el estado devuelto.

## Limitaciones

| Limitacion | Explicacion |
|---|---|
| Depende de Ollama local | Sin Ollama arrancado no hay generacion de respuesta. |
| Modelo configurable | Si `qwen2.5:3b` no esta descargado, hay que ejecutar `ollama pull qwen2.5:3b`. |
| Embeddings iniciales | Son locales y ligeros; no equivalen a modelos semanticos grandes. |
| Calidad condicionada por CSV | El chatbot solo puede responder sobre informacion indexada. |
| Fuentes heterogeneas | Trafikoa es estructurada, Bilbao es institucional, DEIA - Bizkaimove es web de trafico y Bluesky es texto social; la calidad y estabilidad no son equivalentes. |
| Bluesky | Depende de las cuentas seguidas y de la actividad reciente del timeline. |
| Sin motor de rutas | El sistema no calcula rutas completas ni sabe todos los tramos entre origen y destino. Si detecta una pregunta de ruta, lo indica y muestra solo documentos relacionados con las entidades recuperadas. |
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
