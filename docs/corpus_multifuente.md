# Corpus Multifuente De Movilidad Urbana

## Objetivo

El corpus multifuente amplia el proyecto mas alla de Trafikoa. Consolida documentos textuales heterogeneos sobre movilidad urbana en un esquema comun, de forma que puedan validarse como dataset antes de decidir su indexacion en el RAG.

Fuentes implementadas:

| Fuente | Tipo | URL o API |
|---|---|---|
| Ayuntamiento de Bilbao | `web_institucional` | `https://www.bilbao.eus/cs/Satellite?cid=3000075232&language=es&pageid=3000075232&pagename=Bilbaonet%2FPage%2FBIO_ListadoAvisos` |
| DEIA | `medio_digital` | RSS oficial de DEIA, incluyendo `https://www.deia.eus/rss/section/1056166/` |
| Bluesky | `social_media` | API XRPC `app.bsky.feed.searchPosts` |

No se ha implementado Telegram.

## Esquema Comun

| Campo | Descripcion |
|---|---|
| `id` | Identificador estable generado con hash de fuente, URL o texto. |
| `timestamp` | Fecha publicada por la fuente, si existe. |
| `source` | Nombre de la fuente: `Ayuntamiento de Bilbao`, `DEIA` o `Bluesky`. |
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

`src/sources/deia.py` usa RSS oficial. Primero consulta el RSS de trafico de DEIA y despues secciones relacionadas como Bilbao, Bizkaia, Motor, Sociedad y Sucesos. Limpia HTML, filtra noticias por terminos de movilidad y evita falsos positivos evidentes como obras artisticas o cortes de agua sin afeccion viaria.

`src/sources/bluesky.py` usa la API XRPC de Bluesky. Busca posts cortos con terminos como `trafico`, `A-8`, `AP-8`, `Bilbao`, `Bizkaia`, `Euskadi`, `retenciones`, `corte` o `carretera`. Si el endpoint exige autenticacion, no falla el corpus: guarda `data/raw/bluesky_raw.json` con `status=auth_required`. Puede activarse con `BLUESKY_HANDLE` y `BLUESKY_APP_PASSWORD`.

## Institucional, Medio Y Red Social

Las fuentes institucionales tienden a ser mas estables y formales, con menos ruido y mayor trazabilidad. Un medio digital como DEIA aporta contexto narrativo, fechas, titulares y vocabulario periodistico. Bluesky representa texto informal: abreviaturas, mensajes breves, errores, duplicados, subjetividad y variabilidad linguistica.

Esa variabilidad es util para PLN porque permite evaluar limpieza, normalizacion, filtrado semantico, deduplicacion y robustez frente a datos no estructurados. Tambien obliga a documentar calidad y procedencia, no solo cantidad de registros.

## Archivos Generados

| Archivo | Contenido |
|---|---|
| `data/raw/bilbao_raw.json` | Avisos extraidos del Ayuntamiento de Bilbao. |
| `data/raw/deia_raw.json` | Resumen de feeds RSS consultados e items extraidos de DEIA. |
| `data/raw/bluesky_raw.json` | Resultado de busqueda Bluesky o motivo claro si requiere autenticacion. |
| `data/processed/corpus_movilidad.csv` | Corpus consolidado con el esquema comun. |

## Construccion

```powershell
.venv\Scripts\python scripts\build_corpus.py
```

Resultado de referencia obtenido el 12/05/2026:

```text
Corpus multifuente construido: total=19, by_source={'Ayuntamiento de Bilbao': 8, 'DEIA': 11}, errors=[], processed_path=data\processed\corpus_movilidad.csv
```

En esa ejecucion Bluesky genero `bluesky_raw.json`, pero no anadio filas al CSV porque la busqueda requiere autenticacion desde este entorno.

## Endpoints

| Metodo | Endpoint | Descripcion |
|---|---|---|
| `GET` | `/corpus` | Devuelve documentos del corpus consolidado. |
| `POST` | `/corpus/refresh` | Reconstruye Bilbao, DEIA y Bluesky. |

Filtros:

```powershell
curl.exe "http://127.0.0.1:8000/corpus?source=DEIA"
curl.exe "http://127.0.0.1:8000/corpus?source=Bluesky"
curl.exe "http://127.0.0.1:8000/corpus?municipio=Bilbao"
curl.exe "http://127.0.0.1:8000/corpus?tipo_evento=transporte"
```

## Streamlit

La pestana `Corpus multifuente` muestra la tabla consolidada, conteo por fuente y filtros por `source`, `municipio` y `tipo_evento`. El selector de fuente incluye `Ayuntamiento de Bilbao`, `DEIA` y `Bluesky`, aunque Bluesky no tenga filas si la API no permite busqueda anonima.

## Relacion Con RAG

El corpus multifuente no se indexa todavia en ChromaDB. La decision separa dos fases:

1. Consolidar y validar el dataset multifuente.
2. Integrarlo despues en RAG cuando el formato y la calidad esten estabilizados.

## Limitaciones

- Bilbao y DEIA dependen de HTML/RSS vivos que pueden cambiar.
- DEIA puede publicar dias sin noticias relevantes de trafico en el RSS especifico.
- Bluesky puede exigir autenticacion para busqueda; sin credenciales se documenta `auth_required` y el corpus sigue funcionando.
- Los posts sociales son ruidosos: pueden contener ironia, abreviaturas, duplicados, errores ortograficos o contexto insuficiente.
- La clasificacion `tipo_evento` es una regla inicial por palabras clave, no un modelo supervisado.
