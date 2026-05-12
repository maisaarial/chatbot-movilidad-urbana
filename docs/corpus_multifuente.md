# Corpus Multifuente De Movilidad Urbana

## Objetivo

El corpus multifuente amplia el proyecto mas alla de Trafikoa. Consolida documentos textuales heterogeneos sobre movilidad urbana en un esquema comun, de forma que puedan validarse como dataset antes de decidir su indexacion en el RAG.

Fuentes implementadas:

| Fuente | Tipo | URL o API |
|---|---|---|
| Ayuntamiento de Bilbao | `web_institucional` | `https://www.bilbao.eus/cs/Satellite?cid=3000075232&language=es&pageid=3000075232&pagename=Bilbaonet%2FPage%2FBIO_ListadoAvisos` |
| DEIA - Bizkaimove | `trafico_web` | `https://www.deia.eus/servicios/trafico/` con iframe a `https://www.bizkaimove.eus/bm/informacion.html` |
| Bluesky | `social_media` | API XRPC `app.bsky.feed.getTimeline`; `app.bsky.feed.searchPosts` solo como fallback |

No se ha implementado Telegram.

## Esquema Comun

| Campo | Descripcion |
|---|---|
| `id` | Identificador estable generado con hash de fuente, URL o texto. |
| `timestamp` | Fecha publicada por la fuente, si existe. |
| `source` | Nombre de la fuente: `Ayuntamiento de Bilbao`, `DEIA - Bizkaimove` o `Bluesky`. |
| `source_type` | Tipo de fuente: institucional, medio digital o red social. |
| `title` | Titulo del aviso, noticia o post. |
| `text` | Texto principal limpio. |
| `url` | Enlace al documento original o post, si existe. |
| `municipio` | Municipio detectado solo si aparece de forma explicita. |
| `provincia` | Provincia detectada solo si aparece de forma explicita. |
| `carretera` | Carretera detectada, por ejemplo `A-8` o `AP-8`. |
| `tipo_evento` | Clasificacion inicial por reglas: `corte_trafico`, `obras`, `transporte`, `accidente`, `incidencia` o `movilidad`. |
| `raw_text` | Texto base sin estructurar, conservado para trazabilidad. |
| `rag_text` | Texto descriptivo preparado para una futura indexacion. |

Si un campo no puede extraerse de forma fiable, queda vacio. No se inventan datos.

## Conectores

`src/sources/bilbao.py` descarga avisos HTML del Ayuntamiento, extrae fecha, titulo, resumen y URL, y filtra avisos de movilidad.

`src/sources/deia.py` usa como fuente principal la pagina `https://www.deia.eus/servicios/trafico/`. Esa pagina embebe Bizkaimove mediante un iframe hacia `https://www.bizkaimove.eus/bm/inicio.html`; la informacion avanzada se encuentra en `https://www.bizkaimove.eus/bm/informacion.html`. El conector extrae incidencias destacadas si existen, obras, cortes de carril, pasos alternativos, carretera, punto kilometrico, sentido, municipio/zona y enlace PDF de mas informacion cuando esta disponible. El RSS oficial de trafico queda solo como fallback si la pagina interna no devuelve elementos.

`src/sources/bluesky.py` usa la API XRPC de Bluesky. Con `BLUESKY_HANDLE` y `BLUESKY_APP_PASSWORD` configurados en `.env`, el conector inicia sesion y consulta `app.bsky.feed.getTimeline` para leer el timeline de cuentas seguidas, limitado inicialmente a los ultimos 100-150 posts. Esto prioriza cuentas seleccionadas manualmente como relevantes para movilidad en Euskadi y reduce el ruido de la busqueda global. La busqueda `app.bsky.feed.searchPosts` queda solo como fallback opcional si no se puede leer el timeline.

## Institucional, Medio Y Red Social

Las fuentes institucionales tienden a ser mas estables y formales, con menos ruido y mayor trazabilidad. DEIA - Bizkaimove aporta informacion operativa de trafico publicada en una web de servicio: eventos breves, punto kilometrico, carretera, sentido y PDF asociado cuando existe. Bluesky representa texto informal: abreviaturas, mensajes breves, errores, duplicados, subjetividad y variabilidad linguistica.

El filtro de Bluesky acepta terminos en espanol y euskera. Incluye senales como `trafico`, `movilidad`, `accidente`, `retenciones`, `corte`, `obras`, `carril`, `A-8`, `AP-8`, `BI-637`, `N-634`, y tambien `trafikoa`, `zirkulazioa`, `istripua`, `auto-ilarak`, `errepidea`, `mozketa`, `lanak`, `obrak`, `garraioa`, `bidea` o `errei`. No se traduce el texto: se conserva el post original.

Esa variabilidad es util para PLN porque permite evaluar limpieza, normalizacion, filtrado semantico, deduplicacion y robustez frente a datos no estructurados. Tambien obliga a documentar calidad y procedencia, no solo cantidad de registros.

## Archivos Generados

| Archivo | Contenido |
|---|---|
| `data/raw/bilbao_raw.json` | Avisos extraidos del Ayuntamiento de Bilbao. |
| `data/raw/deia_raw.json` | Diagnostico de la pagina DEIA/Bizkaimove, mensajes informativos e items extraidos de informacion avanzada. |
| `data/raw/bluesky_raw.json` | Timeline de Bluesky, estadisticas de filtrado o motivo claro si requiere autenticacion. |
| `data/processed/corpus_movilidad.csv` | Corpus consolidado con el esquema comun. |

## Construccion

```powershell
.venv\Scripts\python scripts\build_corpus.py
```

Resultado de referencia obtenido el 12/05/2026 con credenciales Bluesky configuradas:

```text
Corpus multifuente construido: total=32, by_source={'Ayuntamiento de Bilbao': 8, 'DEIA - Bizkaimove': 22, 'Bluesky': 2}, errors=[], processed_path=data\processed\corpus_movilidad.csv
```

En esa ejecucion DEIA - Bizkaimove devolvio 22 obras o afecciones reales. Bluesky leyo 57 posts del timeline de cuentas seguidas, filtro 2 como relevantes, descarto 55 y no uso fallback global.

## Endpoints

| Metodo | Endpoint | Descripcion |
|---|---|---|
| `GET` | `/corpus` | Devuelve documentos del corpus consolidado. |
| `POST` | `/corpus/refresh` | Reconstruye Bilbao, DEIA - Bizkaimove y Bluesky. |

Filtros:

```powershell
curl.exe "http://127.0.0.1:8000/corpus?source=DEIA%20-%20Bizkaimove"
curl.exe "http://127.0.0.1:8000/corpus?source=Bluesky"
curl.exe "http://127.0.0.1:8000/corpus?municipio=Bilbao"
curl.exe "http://127.0.0.1:8000/corpus?tipo_evento=transporte"
```

## Streamlit

La pestana `Corpus multifuente` muestra la tabla consolidada, conteo por fuente y filtros por `source`, `municipio` y `tipo_evento`. El selector de fuente incluye `Ayuntamiento de Bilbao`, `DEIA - Bizkaimove` y `Bluesky`.

## Relacion Con RAG

El corpus multifuente se indexa en ChromaDB como `document_type=corpus_multifuente` junto con `incidents.csv`, `cameras.csv` y `congestion.csv`. El indexador usa `rag_text` como texto principal; si una fila no lo tiene, construye texto con `title` + `text`.

La metadata preserva `source`, `source_type`, `title`, `url`, `municipio`, `provincia`, `carretera`, `tipo_evento` y `timestamp`. Esto permite que el chatbot cite explicitamente Ayuntamiento de Bilbao, DEIA - Bizkaimove o Bluesky, y que el frontend muestre enlaces clicables cuando existen.

La integracion permite retrieval semantico sobre fuentes heterogeneas: datos estructurados de Trafikoa, avisos institucionales de Bilbao, informacion avanzada de trafico de Bizkaimove y publicaciones sociales de Bluesky.

## Limitaciones

- Bilbao y DEIA - Bizkaimove dependen de HTML vivos que pueden cambiar.
- Si `informacion.html` deja de exponer las obras/incidencias en HTML y pasa a generarlas solo por JavaScript, el conector dejara diagnostico claro en `deia_raw.json`.
- Bluesky requiere credenciales para leer el timeline de cuentas seguidas; sin ellas se documenta `auth_required` y el corpus sigue funcionando.
- La cobertura de Bluesky depende de las cuentas seguidas y de su actividad reciente. Si esas cuentas no publican sobre trafico o movilidad en los ultimos posts, la fuente puede devolver pocos o ningun documento.
- La busqueda global de Bluesky queda como fallback opcional, porque devuelve resultados globales y ruidosos. El filtro exige senal de movilidad y contexto local o carretera vasca.
- Los posts sociales pueden contener ironia, abreviaturas, duplicados, errores ortograficos o contexto insuficiente.
- La clasificacion `tipo_evento` es una regla inicial por palabras clave, no un modelo supervisado.
