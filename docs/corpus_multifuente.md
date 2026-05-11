# Corpus Multifuente De Movilidad Urbana

## Objetivo

El corpus multifuente amplia el proyecto mas alla de Trafikoa. Su finalidad es consolidar documentos textuales heterogeneos sobre movilidad urbana en un unico esquema comun, de forma que en fases posteriores puedan indexarse en el RAG junto con incidencias, camaras y congestion.

En esta primera fase solo se incorpora una fuente externa:

| Fuente | Tipo | URL |
|---|---|---|
| Ayuntamiento de Bilbao | Web institucional | `https://www.bilbao.eus/cs/Satellite?cid=3000075232&language=es&pageid=3000075232&pagename=Bilbaonet%2FPage%2FBIO_ListadoAvisos` |

No se han implementado todavia DEIA, Bluesky ni Telegram.

## Por Que Un Esquema Comun

Cada fuente publica datos con estructuras distintas. Trafikoa usa una API estructurada, mientras que el Ayuntamiento de Bilbao publica avisos como HTML. Para poder mezclar fuentes sin acoplar el resto del sistema a cada formato original, se define un documento normalizado.

El esquema comun permite:

- Comparar documentos de fuentes diferentes.
- Guardar todos los avisos en un CSV consolidado.
- Evitar duplicados con una regla unica.
- Preparar el campo `rag_text` para indexacion futura.
- Mantener trazabilidad hacia la fuente original mediante `url` y `raw_text`.

## Esquema De Documento

| Campo | Descripcion |
|---|---|
| `id` | Identificador estable generado con hash de fuente, URL o texto. |
| `timestamp` | Fecha publicada por la fuente, si existe. |
| `source` | Nombre de la fuente, por ejemplo `Ayuntamiento de Bilbao`. |
| `source_type` | Tipo de fuente, por ejemplo `web_institucional`. |
| `title` | Titulo del aviso o documento. |
| `text` | Texto principal limpio. |
| `url` | Enlace al aviso original. |
| `municipio` | Municipio asociado. En esta fuente: `Bilbao`. |
| `provincia` | Provincia asociada. En esta fuente: `Bizkaia`. |
| `carretera` | Carretera detectada si aparece de forma explicita, por ejemplo `A-8`. |
| `tipo_evento` | Clasificacion inicial: `corte_trafico`, `obras`, `transporte` o `movilidad`. |
| `raw_text` | Texto base sin estructurar, conservado para trazabilidad. |
| `rag_text` | Texto descriptivo preparado para indexacion posterior en RAG. |

Si un campo no puede extraerse de forma fiable, se deja vacio. No se inventan datos.

## Conector De Bilbao

El conector esta en:

```text
src/sources/bilbao.py
```

Responsabilidades principales:

- Descargar la pagina de avisos del Ayuntamiento de Bilbao.
- Extraer fecha, titulo, resumen y URL de cada aviso.
- Limpiar HTML y espacios innecesarios.
- Filtrar avisos relacionados con movilidad, trafico, cortes, obras, aparcamiento, calzada o transporte.
- Evitar que avisos no relacionados, como cortes de agua sin afeccion viaria, entren por palabras demasiado genericas.
- Clasificar el `tipo_evento` con reglas simples por palabras clave.
- Generar `rag_text`.
- Lanzar un error claro si la estructura HTML cambia y no se detecta ningun aviso.

El conector usa `requests` y `HTMLParser` de la libreria estandar. No se ha introducido una dependencia adicional para scraping.

## Archivos Generados

El script de construccion crea estos archivos:

| Archivo | Contenido |
|---|---|
| `data/raw/bilbao_raw.json` | Avisos extraidos de la pagina original y resumen de la extraccion. |
| `data/processed/corpus_movilidad.csv` | Corpus consolidado con el esquema comun. |

## Evitar Duplicados

La deduplicacion se hace en `src/sources/base.py`.

Regla aplicada:

- Si el documento tiene `url`, se usa la URL como clave de duplicado.
- Si no hay URL, se usa un hash del texto (`raw_text` o `text`).

Esto permite incorporar fuentes futuras sin depender de un identificador propio de cada fuente.

## Construccion Del Corpus

Comando:

```powershell
.venv\Scripts\python scripts\build_corpus.py
```

Resultado esperado:

```text
Corpus multifuente construido: total=8, by_source={'Ayuntamiento de Bilbao': 8}, processed_path=data\processed\corpus_movilidad.csv
```

El numero de documentos puede variar porque depende de los avisos publicados por el Ayuntamiento en el momento de la consulta.

## Endpoints

| Metodo | Endpoint | Descripcion |
|---|---|---|
| `GET` | `/corpus` | Devuelve documentos del corpus consolidado. |
| `POST` | `/corpus/refresh` | Reconstruye el corpus ejecutando el conector de Bilbao. |

`GET /corpus` permite filtros opcionales:

```powershell
curl.exe "http://127.0.0.1:8000/corpus?source=Ayuntamiento%20de%20Bilbao"
curl.exe "http://127.0.0.1:8000/corpus?municipio=Bilbao"
curl.exe "http://127.0.0.1:8000/corpus?tipo_evento=corte_trafico"
```

## Integracion En Streamlit

La interfaz incluye la pestana `Corpus multifuente`.

Permite:

- Ver la tabla consolidada.
- Consultar conteo por fuente.
- Filtrar por `source`.
- Filtrar por `municipio`.
- Filtrar por `tipo_evento`.
- Ejecutar `POST /corpus/refresh` con el boton `Actualizar corpus`.

## Relacion Con RAG

En esta fase el corpus multifuente no se indexa todavia en ChromaDB. La decision es intencionada para separar dos pasos:

1. Consolidar y validar el dataset multifuente.
2. Integrarlo despues en el RAG cuando el formato este estable.

El campo `rag_text` ya queda preparado para esa siguiente fase.

## Limitaciones

- La fuente de Bilbao es HTML, no una API JSON estable.
- El parser depende de la estructura actual de la pagina.
- Solo se procesa la pagina principal de avisos, no paginacion historica.
- La clasificacion `tipo_evento` es una primera regla por palabras clave.
- Algunos avisos institucionales pueden contener movilidad de forma indirecta y requerir revision manual.
- Si la pagina cambia y no se detectan avisos, el sistema devuelve un error claro en vez de guardar datos vacios sin explicacion.
