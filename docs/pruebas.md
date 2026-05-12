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

Estas pruebas verifican la integracion de fuentes externas en el corpus comun: Ayuntamiento de Bilbao, DEIA y Bluesky. Bluesky se trata como fuente social no estructurada y no bloqueante.

### Construccion Del Corpus

Comando:

```powershell
.venv\Scripts\python scripts\build_corpus.py
```

Resultado obtenido:

```text
Corpus multifuente construido: total=19, by_source={'Ayuntamiento de Bilbao': 8, 'DEIA': 11}, errors=[], processed_path=data\processed\corpus_movilidad.csv
```

Estado: Paso.

Nota: el numero de documentos puede cambiar porque Bilbao, DEIA y Bluesky son fuentes vivas. En esta ejecucion Bluesky no anadio filas porque la busqueda requiere autenticacion desde este entorno.

### Archivos Generados

Comando:

```powershell
Get-Item data\raw\bilbao_raw.json,data\raw\deia_raw.json,data\raw\bluesky_raw.json,data\processed\corpus_movilidad.csv | Select-Object Name,Length,LastWriteTime
```

Resultado obtenido:

```text
bilbao_raw.json        8781 bytes
deia_raw.json        106180 bytes
bluesky_raw.json        800 bytes
corpus_movilidad.csv  38625 bytes
```

Estado: Paso.

### Validacion Del CSV Consolidado

Comando:

```powershell
.venv\Scripts\python -c "import csv,json,pathlib; rows=list(csv.DictReader(open('data/processed/corpus_movilidad.csv', encoding='utf-8'))); print('rows', len(rows)); print('sources', sorted({r['source'] for r in rows})); print('by_source', {s: sum(1 for r in rows if r['source']==s) for s in sorted({r['source'] for r in rows})}); raw=json.loads(pathlib.Path('data/raw/bluesky_raw.json').read_text(encoding='utf-8')); print('bluesky_status', raw.get('status')); print('bluesky_posts', raw.get('mobility_items'))"
```

Resultado obtenido:

```text
rows 19
sources ['Ayuntamiento de Bilbao', 'DEIA']
by_source {'Ayuntamiento de Bilbao': 8, 'DEIA': 11}
bluesky_status auth_required
bluesky_posts 0
```

Interpretacion:

El corpus contiene documentos reales del Ayuntamiento de Bilbao y DEIA. Bluesky genero `data/raw/bluesky_raw.json`, pero no aparece como `source=Bluesky` en el CSV porque la API de busqueda devolvio autenticacion requerida. El fallo queda documentado y no interrumpe la consolidacion.

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
count=19
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
"deia_count=$($r.by_source.DEIA)"
"errors=$($r.errors.Count)"
```

Resultado obtenido:

```text
count=19
source_count=8
deia_count=11
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
El frontend contiene la pestana Corpus multifuente, el boton Actualizar corpus, filtros por source, municipio y tipo_evento, llamadas a /corpus y /corpus/refresh, y el selector incluye Ayuntamiento de Bilbao, DEIA y Bluesky.
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
RAG index rebuilt: 1412 documents, collection=movilidad_urbana, persist_dir=data\vectorstore
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
documents_indexed=1412
ttl_seconds=300
is_stale=False
status=ready
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
documents_indexed=1412
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
