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
