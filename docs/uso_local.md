# Uso Local

## Activar Entorno Virtual

Desde la raiz del proyecto:

```powershell
.venv\Scripts\activate
```

Si el entorno virtual no existe:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Preparar Configuracion

Copia el archivo de ejemplo:

```powershell
copy .env.example .env
```

Variables importantes:

| Variable | Uso |
|---|---|
| `TRAFIKOA_BASE_URL` | URL base de la API de Trafikoa. |
| `TRAFIKOA_INCIDENTS_PATH` | Ruta de incidencias. |
| `TRAFIKOA_CAMERAS_PATH` | Ruta de camaras. |
| `TRAFIKOA_FLOWS_PATH` | Ruta de flows. |
| `TRAFIKOA_CONGESTION_SOURCE_ID` | Fuente usada para congestion. |
| `CONGESTION_LOW_THRESHOLD` | Umbral bajo de congestion. |
| `CONGESTION_HIGH_THRESHOLD` | Umbral alto de congestion. |

## Arrancar Backend

```powershell
.venv\Scripts\python -m uvicorn backend.main:app --reload
```

URL del backend:

```text
http://127.0.0.1:8000
```

## Abrir Swagger

Con el backend arrancado, abre:

```text
http://127.0.0.1:8000/docs
```

Swagger permite probar los endpoints desde el navegador.

## Arrancar Frontend

En otra terminal:

```powershell
.venv\Scripts\python -m streamlit run frontend/app.py
```

URL del frontend:

```text
http://127.0.0.1:8501
```

## Probar Endpoints

Healthcheck:

```powershell
curl.exe -s "http://127.0.0.1:8000/health"
```

Incidencias:

```powershell
curl.exe -s "http://127.0.0.1:8000/incidencias"
```

Camaras:

```powershell
curl.exe -s "http://127.0.0.1:8000/camaras"
```

Busqueda estructurada de camaras:

```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/camaras/search?q=Bilbao&only_with_image=true"
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/camaras/search?carretera=BI-637&only_with_image=true"
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/camaras/search?municipio=Galdakao"
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/camaras/search?provincia=BIZKAIA"
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/camaras/77"
```

Congestion con datos reales:

```powershell
curl.exe -s "http://127.0.0.1:8000/congestion?max_pages=3"
```

Congestion con valor puntual:

```powershell
curl.exe -s "http://127.0.0.1:8000/congestion?valor=151&umbral_bajo=50&umbral_alto=150"
```

## Usar Chatbot RAG Local

Reconstruye el indice:

```powershell
.venv\Scripts\python scripts\build_rag_index.py
```

Instala o arranca Ollama y descarga el modelo recomendado:

```powershell
ollama pull qwen2.5:3b
```

Configuracion recomendada en `.env`:

```text
OLLAMA_MODEL=qwen2.5:3b
OLLAMA_TIMEOUT=180
RAG_INDEX_TTL_SECONDS=300
```

Prueba el endpoint:

```powershell
$body = @{ question = "Hay incidencias en la A-8?" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/chat" -Body $body -ContentType "application/json"
```

Ejemplos de chat para camaras:

```powershell
$body = @{ question = "Muestrame camaras en Bilbao" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/chat" -Body $body -ContentType "application/json"

$body = @{ question = "Que camaras hay en la A-8?" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/chat" -Body $body -ContentType "application/json"
```

Consulta el estado del indice RAG:

```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/rag/status"
```

Reconstruye el indice manualmente:

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/rag/refresh"
```

## Apagar Servidores

Si los servidores estan en terminales abiertas, usa:

```text
Ctrl + C
```

Si estan ejecutandose en segundo plano, puedes localizar procesos:

```powershell
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*uvicorn*backend.main*' -or $_.CommandLine -like '*streamlit*frontend/app.py*' } | Select-Object ProcessId,CommandLine
```

Y detenerlos:

```powershell
Stop-Process -Id <PID> -Force
```

## Errores Comunes

### Puerto 8000 Ocupado

Sintoma:

```text
Address already in use
```

Comprobar puerto:

```powershell
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
```

Solucion:

- Cerrar el backend anterior.
- O arrancar en otro puerto:

```powershell
.venv\Scripts\python -m uvicorn backend.main:app --reload --port 8001
```

### Puerto 8501 Ocupado

Comprobar puerto:

```powershell
Get-NetTCPConnection -LocalPort 8501 -ErrorAction SilentlyContinue
```

Arrancar Streamlit en otro puerto:

```powershell
.venv\Scripts\python -m streamlit run frontend/app.py --server.port 8502
```

### No Hay Conexion Con Trafikoa

Sintoma:

```text
502 Bad Gateway
```

Posibles causas:

- Sin conexion a internet.
- Timeout de la API.
- Endpoint temporalmente no disponible.

Prueba directa:

```powershell
curl.exe -s "https://api.euskadi.eus/traffic/v1.0/sources"
```

### Descarga De Congestion Lenta

Los endpoints de `flows` pueden tener muchas paginas. Para pruebas se recomienda limitar:

```powershell
curl.exe -s "http://127.0.0.1:8000/congestion?max_pages=3"
```

Para una descarga mas amplia, aumenta `max_pages` con cuidado.
