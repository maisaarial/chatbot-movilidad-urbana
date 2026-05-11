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

### Error Controlado Si Ollama No Esta Disponible

Comportamiento esperado si Ollama no esta instalado, no esta arrancado o el modelo no esta descargado:

```text
HTTP 503 con mensaje indicando que no se pudo conectar con Ollama y que se debe ejecutar:
ollama pull qwen2.5:3b
```

Estado: implementado en `src/rag/ollama_client.py` y expuesto por `backend/main.py`.
