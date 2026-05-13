# Pruebas Realizadas

## Objetivo

Las pruebas basicas verifican que el proyecto arranca, consulta Trafikoa, genera archivos y muestra datos en el frontend.

Las pruebas se ejecutaron en PowerShell sobre Windows, dentro del directorio del proyecto.

## Pruebas Iniciales

Resultado global:

```text
7/7 pruebas iniciales pasadas
```

| Prueba | Comando | Resultado | Estado |
|---|---|---|---|
| Backend arrancado | `Get-NetTCPConnection -LocalPort 8000,8501 -ErrorAction SilentlyContinue` | `127.0.0.1:8000 Listen` | Paso |
| Healthcheck | `curl.exe -s --max-time 10 "http://127.0.0.1:8000/health"` | `{"status":"ok"}` | Paso |
| Incidencias reales | `$r = curl.exe -s --max-time 90 "http://127.0.0.1:8000/incidencias" \| ConvertFrom-Json; "count=$($r.count)"` | `count=417` | Paso |
| Camaras reales | `$r = curl.exe -s --max-time 90 "http://127.0.0.1:8000/camaras" \| ConvertFrom-Json; "count=$($r.count)"` | `count=489` | Paso |
| Archivos generados | `Get-Item data/raw/incidents_raw.json, data/processed/incidents.csv, data/raw/cameras_raw.json, data/processed/cameras.csv` | Existen todos | Paso |
| Frontend Streamlit | `curl.exe -I --max-time 10 "http://127.0.0.1:8501"` | `HTTP/1.1 200 OK` | Paso |
| Camaras con imagen | `$cams = @($r.items \| Where-Object { $_.image_url })` | `cameras_with_image=390` | Paso |

## Comprobacion De Imagen De Camara

Comando:

```powershell
curl.exe -I --max-time 15 "http://www.bizkaimove.com/camaras/cam1.jpg"
```

Resultado:

```text
HTTP/1.1 200 OK
Content-Type: image/jpeg
```

Esto confirma que al menos una camara seleccionable tiene una URL de imagen valida.

## Pruebas De Congestion

### Funcion De Umbrales

Comando:

```powershell
.venv\Scripts\python -c "from src.congestion import calcular_congestion; print(calcular_congestion(10, 50, 150).value); print(calcular_congestion(50, 50, 150).value); print(calcular_congestion(150, 50, 150).value)"
```

Resultado:

```text
baja
media
alta
```

Estado: Paso.

### Endpoint De Congestion Con Datos Reales

Comando:

```powershell
$r = curl.exe -s --max-time 120 "http://127.0.0.1:8000/congestion?max_pages=3" | ConvertFrom-Json
"count=$($r.count)"
"low=$(@($r.items | Where-Object { $_.congestion -eq 'baja' }).Count)"
"medium=$(@($r.items | Where-Object { $_.congestion -eq 'media' }).Count)"
"high=$(@($r.items | Where-Object { $_.congestion -eq 'alta' }).Count)"
```

Resultado:

```text
count=60
low=28
medium=27
high=5
```

Primera fila:

```text
2026-05-11T05:45 | medidor:248 | 0.0 | baja
```

Estado: Paso.

### Clasificacion Puntual

Comando:

```powershell
$r = curl.exe -s --max-time 10 "http://127.0.0.1:8000/congestion?valor=151&umbral_bajo=50&umbral_alto=150" | ConvertFrom-Json
"level=$($r.level)"
```

Resultado:

```text
level=alta
```

Estado: Paso.

### CSV De Congestion

Comando:

```powershell
Get-Content data\processed\congestion.csv -TotalCount 3
```

Resultado:

```text
timestamp,carretera,municipio,provincia,valor_trafico,unidad,congestion,fuente,rag_text
2026-05-11T05:45,medidor:248,Bilbao,Bizkaia,0.0,vehiculos/intervalo,baja,Ayuntamiento Bilbao,...
2026-05-11T08:25,medidor:248,Bilbao,Bizkaia,86.0,vehiculos/intervalo,media,Ayuntamiento Bilbao,...
```

Estado: Paso.

## Como Repetir Las Pruebas

1. Activa el entorno virtual:

```powershell
.venv\Scripts\activate
```

2. Arranca el backend:

```powershell
.venv\Scripts\python -m uvicorn backend.main:app --reload
```

3. En otra terminal, arranca el frontend:

```powershell
.venv\Scripts\python -m streamlit run frontend/app.py
```

4. Ejecuta pruebas basicas:

```powershell
curl.exe -s "http://127.0.0.1:8000/health"
curl.exe -s "http://127.0.0.1:8000/incidencias"
curl.exe -s "http://127.0.0.1:8000/camaras"
curl.exe -s "http://127.0.0.1:8000/congestion?max_pages=3"
```

5. Comprueba archivos:

```powershell
Get-Item data\raw\incidents_raw.json
Get-Item data\processed\incidents.csv
Get-Item data\raw\cameras_raw.json
Get-Item data\processed\cameras.csv
Get-Item data\raw\congestion_raw.json
Get-Item data\processed\congestion.csv
```

## Pruebas Del Corpus Multifuente

Estas pruebas verifican la integracion de fuentes externas en el corpus comun: Ayuntamiento de Bilbao, DEIA - Bizkaimove y Bluesky. Bluesky se trata como fuente social no estructurada y no bloqueante. La fuente principal de Bluesky es el timeline de cuentas seguidas, no la busqueda global.

### Construccion Del Corpus

Comando:

```powershell
.venv\Scripts\python scripts\build_corpus.py
```

Resultado obtenido:

```text
Corpus multifuente construido: total=32, by_source={'Ayuntamiento de Bilbao': 8, 'DEIA - Bizkaimove': 22, 'Bluesky': 2}, errors=[], processed_path=data\processed\corpus_movilidad.csv
```

Estado: Paso.

Nota: el numero de documentos puede cambiar porque Bilbao, DEIA - Bizkaimove y Bluesky son fuentes vivas. En esta ejecucion Bluesky uso credenciales reales desde `.env`, leyo 57 posts del timeline de cuentas seguidas, filtro 2 como relevantes, descarto 55 y no uso fallback global.

### Archivos Generados

Comando:

```powershell
Get-Item data\raw\bilbao_raw.json,data\raw\deia_raw.json,data\raw\bluesky_raw.json,data\processed\corpus_movilidad.csv | Select-Object Name,Length,LastWriteTime
```

Resultado obtenido:

```text
bilbao_raw.json        8781 bytes
deia_raw.json          8507 bytes
bluesky_raw.json      60253 bytes
corpus_movilidad.csv  32577 bytes
```

Estado: Paso.

### Validacion Del CSV Consolidado

Comando:

```powershell
.venv\Scripts\python -c "import csv,json,pathlib; rows=list(csv.DictReader(open('data/processed/corpus_movilidad.csv', encoding='utf-8'))); print('rows', len(rows)); print('sources', sorted({r['source'] for r in rows})); print('by_source', {s: sum(1 for r in rows if r['source']==s) for s in sorted({r['source'] for r in rows})}); raw=json.loads(pathlib.Path('data/raw/bluesky_raw.json').read_text(encoding='utf-8')); print('bluesky_status', raw.get('status')); print('bluesky_posts', raw.get('mobility_items')); print('posts_read_timeline', raw.get('posts_read_timeline')); print('posts_discarded', raw.get('posts_discarded')); print('fallback_used', raw.get('fallback_used'))"
```

Resultado obtenido:

```text
rows 32
sources ['Ayuntamiento de Bilbao', 'Bluesky', 'DEIA - Bizkaimove']
by_source {'Ayuntamiento de Bilbao': 8, 'Bluesky': 2, 'DEIA - Bizkaimove': 22}
bluesky_status ok
bluesky_posts 2
posts_read_timeline 57
posts_discarded 55
fallback_used False
```

Interpretacion:

El corpus contiene documentos reales del Ayuntamiento de Bilbao, DEIA - Bizkaimove y Bluesky. DEIA extrae obras/cortes/pasos alternativos desde `https://www.bizkaimove.eus/bm/informacion.html` y registra en raw mensajes como `No existen incidencias destacadas.`. Bluesky recupero posts del timeline mediante API autenticada y aplica filtros en espanol/euskera para conservar mensajes con senal de movilidad y contexto local, sin traducir el texto original.

Estado: Paso.

### GET `/corpus`

Comando:

```powershell
$r = curl.exe -s --max-time 30 "http://127.0.0.1:8000/corpus" | ConvertFrom-Json
"count=$($r.count)"
"first_source=$($r.items[0].source)"
"first_tipo=$($r.items[0].tipo_evento)"
```

Resultado obtenido:

```text
count=32
first_source=Ayuntamiento de Bilbao
first_tipo=corte_trafico
```

Estado: Paso.

### POST `/corpus/refresh`

Comando:

```powershell
$r = curl.exe -s --max-time 120 -X POST "http://127.0.0.1:8000/corpus/refresh" | ConvertFrom-Json
"count=$($r.count)"
"source_count=$($r.by_source.'Ayuntamiento de Bilbao')"
"deia_count=$($r.by_source.'DEIA - Bizkaimove')"
"bluesky_count=$($r.by_source.Bluesky)"
"errors=$($r.errors.Count)"
```

Resultado obtenido:

```text
count=32
source_count=8
deia_count=22
bluesky_count=2
errors=0
```

Estado: Paso.

### Frontend Con Pestana Corpus Multifuente

Comandos:

```powershell
curl.exe -I --max-time 10 "http://127.0.0.1:8501"
Select-String -Path frontend\app.py -Pattern "Corpus multifuente|Actualizar corpus|tipo_evento|/corpus/refresh|/corpus"
```

Resultado obtenido:

```text
HTTP/1.1 200 OK
El frontend contiene la pestana Corpus multifuente, el boton Actualizar corpus, filtros por source, municipio y tipo_evento, llamadas a /corpus y /corpus/refresh, y el selector incluye Ayuntamiento de Bilbao, DEIA - Bizkaimove y Bluesky.
```

Estado: Paso.

## Pruebas Del Chatbot RAG

### Reconstruccion Del Indice

Comando:

```powershell
.venv\Scripts\python scripts\build_rag_index.py
```

Resultado obtenido:

```text
RAG index rebuilt: 1328 documents, collection=movilidad_urbana, persist_dir=data\vectorstore
Document types indexed: {'incidencia': 307, 'camara': 489, 'congestion': 500, 'corpus_multifuente': 32}
Sources indexed: {'Gobierno Pais Vasco': 136, 'Ayuntamiento Bilbao': 630, 'Trafikoa': 489, 'Ayuntamiento de Bilbao': 8, 'DEIA - Bizkaimove': 22, 'Bluesky': 2, ...}
```

Estado: Paso.

### Recuperacion Con Consulta `A-8`

Comando:

```powershell
.venv\Scripts\python -c "from src.rag.retriever import retrieve; results=retrieve('A-8', k=5); print('results', len(results)); [print(i+1, r['metadata'].get('document_type'), r['metadata'].get('carretera'), r['distance'], r['text'][:140].replace('\n',' ')) for i,r in enumerate(results)]"
```

Resultado obtenido:

```text
results 5
1 incidencia A-8 0.0 id: 363423...
2 incidencia A-8 0.0 id: 363420...
3 incidencia A-8 0.0 id: 363409...
4 incidencia A-8 0.0 id: 363408...
5 incidencia A-8 0.0 id: 363407...
```

Estado: Paso.

### Estado Del Indice RAG

Comando:

```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/rag/status" -TimeoutSec 20 | ConvertTo-Json -Depth 5
```

Resultado obtenido:

```text
documents_indexed=1328
ttl_seconds=300
is_stale=False
status=ready
corpus_multifuente=32
```

Estado: Paso.

### Refresco Manual Del Indice RAG

Comando:

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/rag/refresh" -TimeoutSec 180 | ConvertTo-Json -Depth 5
```

Resultado obtenido:

```text
refreshed=True
last_refresh_reason=manual
documents_indexed=1328
is_stale=False
```

Estado: Paso.

### Refresco Automatico Por TTL

Para no esperar 5 minutos reales, se forzo temporalmente una fecha antigua en `data/vectorstore/rag_status.json`.

Comando:

```powershell
.venv\Scripts\python -c "import json, pathlib; p=pathlib.Path('data/vectorstore/rag_status.json'); s=json.loads(p.read_text(encoding='utf-8')); s['last_refresh_at']='2000-01-01T00:00:00+00:00'; p.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding='utf-8'); print('status forced stale')"
$s = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/rag/status" -TimeoutSec 20
"before stale=$($s.is_stale)"
$r = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/rag/search?query=A-8&limit=2" -TimeoutSec 180
"after refreshed=$($r.index_status.refreshed) reason=$($r.index_status.last_refresh_reason) stale=$($r.index_status.is_stale) results=$($r.results.Count)"
```

Resultado obtenido:

```text
before stale=True
after refreshed=True reason=ttl_expired stale=False results=2
```

Interpretacion:

El endpoint de busqueda detecto que el indice habia caducado y lo reconstruyo automaticamente antes de devolver resultados.

Estado: Paso.

### Chat Con Corpus Multifuente

Comando:

```powershell
$questions = @(
  "¿Qué cortes recientes hay en Bilbao?",
  "¿Qué obras o cortes aparecen en Bizkaimove?",
  "¿Qué información reciente hay en Bluesky sobre movilidad?",
  "¿Qué noticias o avisos hay sobre movilidad?"
)
foreach ($q in $questions) {
  $body = @{ question = $q } | ConvertTo-Json
  $r = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/chat" -Body $body -ContentType "application/json" -TimeoutSec 240
  $r.sources | Select-Object -First 3 -ExpandProperty metadata | Select-Object source,source_type,title,url,tipo_evento,timestamp
}
```

Resultado obtenido:

```text
Bilbao: usa Ayuntamiento de Bilbao con titulos reales y URLs de avisos.
Bizkaimove: usa DEIA - Bizkaimove con titulos como "Un carril cortado (SONDIKA)" y enlaces PDF o informacion.html.
Bluesky: usa publicaciones sociales, muestra autor en el titulo/metadata y URLs bsky.app.
Noticias o avisos: recupera corpus_multifuente y cita source, source_type, title, url, tipo_evento y timestamp.
```

Estado: Paso.

### Camaras Siguen Usando Busqueda Estructurada

Comando:

```powershell
$body = @{ question = "¿Qué cámaras hay en Bilbao?" } | ConvertTo-Json
$r = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/chat" -Body $body -ContentType "application/json" -TimeoutSec 120
$r.sources[0].metadata.document_type
$r.sources[0].metadata.image_url
```

Resultado obtenido:

```text
document_type=camara
image_url=http://www.bizkaimove.com/camaras/cam51.jpg
```

Estado: Paso.

## Pruebas De Evaluacion

### Dataset Manual

Archivo:

```text
data/evaluation/eval_queries.csv
```

Resultado:

```text
25 preguntas anotadas manualmente
columnas=id, question, expected_intent, expected_entities, expected_source_type, expected_source, expected_answer_contains, notes
```

La muestra incluye incidencias Trafikoa, camaras, congestion, avisos Ayuntamiento de Bilbao, DEIA - Bizkaimove, Bluesky y preguntas sin informacion suficiente.

Estado: Paso.

### Evaluacion De Retrieval

Comando:

```powershell
.venv\Scripts\python scripts\evaluate_retrieval.py
```

Resultado obtenido:

```text
retrieval_queries=25
metric_applicable=23
recall@5=0.652
mrr@5=0.630
output=data\evaluation\retrieval_results.csv
```

Interpretacion:

El retrieval recupera la fuente o tipo esperado en 15 de 23 preguntas con metrica aplicable. Los fallos principales aparecen en consultas ambiguas o en camaras, porque el flujo final de camaras no depende solo del retrieval semantico: usa busqueda estructurada antes del RAG.

Estado: Paso.

### Evaluacion Del Chatbot

Comando:

```powershell
.venv\Scripts\python scripts\evaluate_chatbot.py
```

Resultado obtenido:

```text
chatbot_queries=25
completed=25
contains_expected_rate=0.840
expected_source_rate=0.800
output=data\evaluation\chatbot_results.csv
```

Interpretacion:

El chatbot completa todas las preguntas. La comprobacion automatica de terminos esperados pasa en 21 de 25 casos. La fuente esperada aparece en 20 de 25 casos tras corregir la metadata `source=Trafikoa` en respuestas de camaras. Quedan fallos reales en consultas de congestion ambiguas y en una pregunta social amplia sobre Bizkaia que recupera antes avisos institucionales que Bluesky.

Estado: Paso.

## Pruebas De Busqueda Estructurada De Camaras

### Auditoria De Campos De Camaras

Comando:

```powershell
$csv = Import-Csv data\processed\cameras.csv
"rows=$($csv.Count)"
"columns=$((($csv | Get-Member -MemberType NoteProperty).Name) -join ', ')"
"with_image_url=$(@($csv | Where-Object { $_.image_url -and $_.image_url.Trim() }).Count)"
"with_stream_url=$(@($csv | Where-Object { $_.stream_url -and $_.stream_url.Trim() }).Count)"
"with_lat_lon=$(@($csv | Where-Object { $_.latitude -and $_.longitude }).Count)"
```

Resultado obtenido:

```text
rows=489
columns=carretera, id, image_url, kilometer, latitude, longitude, municipio, nombre, provincia, raw_latitude, raw_longitude, source_id, source_url, stream_url
with_image_url=390
with_stream_url=0
with_lat_lon=489
```

Interpretacion:

La API real trae `urlImage` para 390 camaras. No se detectaron campos `imageUrl`, `cameraUrl` ni `stream_url` en el JSON crudo probado. `urlImage` se conserva como `image_url`.

Estado: Paso.

### GET `/camaras/search?q=Bilbao`

Comando:

```powershell
$r = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/camaras/search?q=Bilbao&only_with_image=true&limit=5" -TimeoutSec 30
"count=$($r.count)"
"all_have_image=$(@($r.items | Where-Object { -not $_.image_url }).Count -eq 0)"
$r.items[0] | ConvertTo-Json -Depth 4
```

Resultado obtenido:

```text
count=5
all_have_image=True
id=95
nombre=Cctv 406 - DOMO Enekuri
carretera=BI-604
municipio=Bilbao
provincia=Bizkaia
image_url=http://www.bizkaimove.com/camaras/cam51.jpg
maps_url=https://www.google.com/maps?q=43.29239403,-2.95937195
```

Estado: Paso.

### GET `/camaras/search?carretera=BI-637&only_with_image=true`

Comando:

```powershell
$r = Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/camaras/search?carretera=BI-637&only_with_image=true&limit=5" -TimeoutSec 30
"count=$($r.count)"
"all_have_image=$(@($r.items | Where-Object { -not $_.image_url }).Count -eq 0)"
$r.items[0] | ConvertTo-Json -Depth 4
```

Resultado obtenido:

```text
count=5
all_have_image=True
id=77
nombre=CCTV 300 - Camara DOMO nudo Kukularra
carretera=BI-637
image_url=http://www.bizkaimove.com/camaras/cam1.jpg
maps_url=https://www.google.com/maps?q=43.30481703,-2.96080601
```

Estado: Paso.

### POST `/chat` Con Camaras En Bilbao

Comando:

```powershell
$body = @{ question = "Muestrame camaras en Bilbao" } | ConvertTo-Json
$r = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/chat" -Body $body -ContentType "application/json; charset=utf-8" -TimeoutSec 240
$r.answer
"sources=$($r.sources.Count)"
```

Resultado obtenido:

```text
Si. Encontre estas camaras:
1. Nombre: Cctv 406 - DOMO Enekuri
   Carretera: BI-604
   Municipio/provincia: Bilbao / Bizkaia
   Imagen: http://www.bizkaimove.com/camaras/cam51.jpg
   Mapa: https://www.google.com/maps?q=43.29239403,-2.95937195
sources=10
```

Estado: Paso.

### Camara Existente Sin Imagen

Comando:

```powershell
$body = @{ question = "Hay camara CCTV 232?" } | ConvertTo-Json
$r = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/chat" -Body $body -ContentType "application/json; charset=utf-8" -TimeoutSec 240
$r.answer
```

Resultado obtenido:

```text
Si. Encontre estas camaras:
Las camaras encontradas existen en la API, pero no tienen imagen disponible.
1. Nombre: CCTV 232 - Camara DOMO 232
   Carretera: N - 637
   Municipio/provincia: Cruces / Bizkaia
   Imagen: no hay imagen disponible
   Mapa: https://www.google.com/maps?q=43.28936698,-2.90569902
```

Estado: Paso.

### POST `/chat` Con Camaras En La A-8

Comando:

```powershell
$body = @{ question = "Que camaras hay en la A-8?" } | ConvertTo-Json
$r = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/chat" -Body $body -ContentType "application/json; charset=utf-8" -TimeoutSec 240
$r.answer
"sources=$($r.sources.Count)"
```

Resultado obtenido:

```text
Si. Encontre estas camaras:
1. Nombre: Iurreta
   Carretera: A-8
   Municipio/provincia: no disponible / no disponible
   Imagen: https://www.trafikoa.eus/static/files/tr/camaras/819.jpg
   Mapa: https://www.google.com/maps?q=43.18725,-2.673754
sources=10
```

Estado: Paso.

### Imagen Real De Camara

Comando:

```powershell
curl.exe -I --max-time 15 "http://www.bizkaimove.com/camaras/cam1.jpg"
```

Resultado obtenido:

```text
HTTP/1.1 200 OK
Content-Type: image/jpeg
```

Estado: Paso.

### Detalle De Camara Por ID

Comando:

```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/camaras/77" -TimeoutSec 30 | Select-Object id,nombre,image_url,maps_url,source_id,kilometer | ConvertTo-Json
```

Resultado obtenido:

```text
id=77
nombre=CCTV 300 - Camara DOMO nudo Kukularra
image_url=http://www.bizkaimove.com/camaras/cam1.jpg
maps_url=https://www.google.com/maps?q=43.30481703,-2.96080601
source_id=2
kilometer=008+500
```

Estado: Paso.

### Frontend De Camaras

Comandos:

```powershell
curl.exe -I --max-time 10 "http://127.0.0.1:8501"
Select-String -Path frontend\app.py -Pattern "st.image\(|Ver imagen original|Ver en Google Maps|Buscar camaras"
```

Resultado obtenido:

```text
HTTP/1.1 200 OK
El frontend contiene buscador de camaras, checkbox "Mostrar solo camaras con imagen", renderizado con st.image, link de imagen original, source_url y link a Google Maps.
```

Estado: Paso.

### Comprobacion De Ollama

Comando:

```powershell
curl.exe -s --max-time 5 "http://localhost:11434/api/tags"
```

Resultado obtenido en este entorno:

```json
{
  "models": [
    {
      "name": "qwen2.5:3b",
      "model": "qwen2.5:3b"
    }
  ]
}
```

Interpretacion:

El servicio local de Ollama esta arrancado en `http://localhost:11434` y el modelo `qwen2.5:3b` esta disponible. En este equipo el comando `ollama --version` no esta disponible en PowerShell porque el ejecutable no esta en el `PATH`, pero la API local si responde correctamente.

Si el modelo no apareciera en la lista, el comando necesario seria:

```powershell
ollama pull qwen2.5:3b
```

Estado: Paso.

### POST `/chat`

Antes de repetir la prueba se ajusto `OLLAMA_TIMEOUT=180` para dar margen suficiente a la generacion local y se limito la respuesta con `num_predict=220`.

Comando:

```powershell
$body = @{ question = "¿Hay incidencias en la A-8?" } | ConvertTo-Json
$r = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/chat" -Body $body -ContentType "application/json; charset=utf-8" -TimeoutSec 240
$answer = $r.answer
$checks = @("Tipo:", "Causa:", "Sentido:", "Municipio/provincia:", "Fecha/hora:")
$missing = @($checks | Where-Object { $answer -notlike "*$_*" })
$answer
"sources=$($r.sources.Count)"
if ($missing.Count -eq 0 -and $r.sources.Count -gt 0) { "detalle=paso" } else { "detalle=falla" }
```

Resultado obtenido:

```text
Si. Segun las fuentes recuperadas, se encontraron estas incidencias:
1. Tipo: Accidente
   Carretera: A-8
   Causa: Salida
   Sentido: Irun
   Municipio/provincia: Bilbao / BIZKAIA
   Fecha/hora: 2026-05-11T17:28
2. Tipo: Accidente
   Carretera: A-8
   Causa: Alcance
   Sentido: Irun
   Municipio/provincia: Galdakao / BIZKAIA
   Fecha/hora: 2026-05-11T16:47:35
...
sources=5
detalle=paso
```

Interpretacion:

La respuesta ya no es una afirmacion generica. Enumera las incidencias recuperadas y contiene campos concretos: tipo, carretera, causa, sentido, municipio/provincia y fecha/hora.

Estado: Paso.

### Pregunta Fuera De Dominio

Comando:

```powershell
$body = @{ question = "Cual es la poblacion de Paris?" } | ConvertTo-Json
$r = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/chat" -Body $body -ContentType "application/json" -TimeoutSec 180
"answer=$($r.answer)"
"sources=$($r.sources.Count)"
```

Resultado obtenido:

```text
answer=No encontre informacion suficiente en las fuentes disponibles.
sources=0
```

Estado: Paso.

### Frontend Con Pestaña Chatbot

Comando:

```powershell
curl.exe -I --max-time 10 "http://127.0.0.1:8501"
```

Resultado obtenido:

```text
HTTP/1.1 200 OK
Server: TornadoServer/6.5.5
```

Estado: Paso.

La pestana `RAG` tambien incluye el boton `Actualizar indice RAG ahora`, que llama a `POST /rag/refresh` y muestra el estado actualizado del indice.

### Error Controlado Si Ollama No Esta Disponible

Comportamiento esperado si Ollama no esta instalado, no esta arrancado o el modelo no esta descargado:

```text
HTTP 503 con mensaje indicando que no se pudo conectar con Ollama y que se debe ejecutar:
ollama pull qwen2.5:3b
```

Estado: implementado en `src/rag/ollama_client.py` y expuesto por `backend/main.py`.

## Pruebas De Query Understanding, Filtrado Y Reranking

Objetivo: comprobar que el chatbot interpreta intencion y entidades antes del LLM, evita mezclar camaras cuando no se pidieron y avisa cuando no hay coincidencia exacta.

Comando usado en modo directo, sin forzar refresco del indice:

```powershell
.venv\Scripts\python.exe -B -c "import os; os.environ['RAG_INDEX_TTL_SECONDS']='999999'; from src.rag.chatbot import answer_question; import json; qs=['Lekeitio','¿Hay congestión en la vía a Lekeitio desde Bilbao?','¿Hay incidencias en la BI-2405?','¿Qué obras hay en Bizkaimove?','Muéstrame cámaras en Bilbao','¿Hay cortes en Alameda Recalde?']; print(json.dumps([answer_question(q) for q in qs], ensure_ascii=False, indent=2))"
```

### `Lekeitio`

Resultado observado:

```text
intent=general
lugares=[Lekeitio]
sources=2
tipos=incidencia, corpus_multifuente
carreteras=BI-2405
```

Interpretacion: prioriza la incidencia de BI-2405 con sentido Lekeitio y el documento de DEIA - Bizkaimove en Amoroto. No mezcla camaras ni congestion de Bilbao.

Estado: Paso.

### `¿Hay congestión en la vía a Lekeitio desde Bilbao?`

Resultado observado:

```text
intent=congestion
is_route=true
route_from=Bilbao
route_to=Lekeitio
fallback_used=true
strict_result_count=0
sources=2
tipos=incidencia, corpus_multifuente
carreteras=BI-2405
```

La respuesta empieza indicando que no hay calculo de ruta completo y que no se encontraron registros de congestion especificos para esa ruta. Despues muestra solo informacion relacionada con Lekeitio/BI-2405.

Estado: Paso.

### `¿Hay incidencias en la BI-2405?`

Resultado observado:

```text
intent=incidencias
carreteras=[BI-2405]
fallback_used=false
strict_result_count=3
tipos=incidencia
```

Interpretacion: recupera incidencias de BI-2405, incluyendo la incidencia de Amoroto sentido Lekeitio.

Estado: Paso.

### `¿Qué obras hay en Bizkaimove?`

Resultado observado:

```text
intent=obras_cortes
source_preference=DEIA - Bizkaimove
fallback_used=false
tipos=corpus_multifuente
source=DEIA - Bizkaimove
```

Interpretacion: prioriza el corpus multifuente de DEIA - Bizkaimove y no mezcla camaras.

Estado: Paso.

### `Muéstrame cámaras en Bilbao`

Resultado observado:

```text
intent=camaras
lugares=[Bilbao]
flujo=busqueda estructurada de camaras
sources=10
tipos=camara
```

Interpretacion: mantiene la busqueda estructurada de camaras y devuelve imagenes/mapas reales del CSV procesado.

Estado: Paso.

### `¿Hay cortes en Alameda Recalde?`

Resultado observado:

```text
intent=obras_cortes
lugares=[Alameda Recalde]
fallback_used=false
strict_result_count=1
source=Ayuntamiento de Bilbao
tipo_evento=corte_trafico
```

Interpretacion: recupera el aviso especifico del Ayuntamiento de Bilbao sobre el corte de dos carriles en Alameda Recalde.

Estado: Paso.

## Pruebas De Estilo De Respuesta

Objetivo: comprobar que la respuesta principal se redacta de forma natural y que la metadata completa queda separada en `Fuentes usadas`.

Comando:

```powershell
.venv\Scripts\python.exe -B -c "import os; os.environ['RAG_INDEX_TTL_SECONDS']='999999'; from src.rag.chatbot import answer_question; qs=['¿Hay cortes en Alameda Recalde?','¿Qué obras hay en Bizkaimove?','¿Hay incidencias en la BI-2405?','¿Hay congestión en la vía a Lekeitio desde Bilbao?']; forbidden=['Documento multifuente','Tipo de fuente','source_type','document_type']; [print('---', q, '\n', answer_question(q)['answer'], '\nforbidden=', [x for x in forbidden if x in answer_question(q)['answer']]) for q in qs]"
```

Resultados observados:

```text
¿Hay cortes en Alameda Recalde?
Sí. El Ayuntamiento de Bilbao informa de un corte de dos carriles en Alameda Recalde, en sentido Plaza Moyúa. El aviso está fechado el 11 de mayo de 2026.
forbidden=[]

¿Qué obras hay en Bizkaimove?
Bizkaimove recoge varias afecciones de obra o cortes. Entre ellas: un carril cortado en Sondika en la BI-30, un paso alternativo en Mallabia en la N-634, un sentido cortado en Bilbao en la BI-636, un carril cortado en Ermua en la N-634 y un arcén cortado en Galdakao en la N-634.
forbidden=[]

¿Hay incidencias en la BI-2405?
Sí. En la BI-2405 se encontraron varias incidencias: registros de puerto de montaña sin causa detallada y un accidente por alcance en sentido Lekeitio, en Amoroto.
forbidden=[]

¿Hay congestión en la vía a Lekeitio desde Bilbao?
No dispongo de cálculo de ruta completo para Bilbao - Lekeitio, pero encontré información relacionada.
No encontré información específica para esa ubicación en las fuentes disponibles. Muestro solo coincidencias relacionadas, no una confirmación exacta.
No encontré registros de congestión específicos para esa ubicación o ruta.
Incidencias: Sí. En Bilbao - Lekeitio se encontró un accidente por alcance en sentido Lekeitio, en Amoroto.
Obras/cortes: Sí. Bizkaimove informa de un paso alternativo en Amoroto en la BI-2405, en sentido Lekeitio - Plazakola. El aviso está fechado el 2026-05-13T10:18:43.216055+00:00.
forbidden=[]
```

Interpretacion: la respuesta principal ya no repite `Documento multifuente`, `Tipo de fuente`, `source_type` ni `document_type`. Las fuentes completas, enlaces y metadata siguen disponibles en la seccion `Fuentes usadas` porque el endpoint conserva el array `sources`.

Estado: Paso.
