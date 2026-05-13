# Vision Por Computador

## Objetivo

El proyecto incorpora una primera funcionalidad de vision por computador para analizar imagenes de camaras de trafico y generar alertas preliminares de posibles anomalias visuales.

La salida nunca debe afirmar con certeza que hay un accidente. Si las reglas detectan senales relevantes, se usa lenguaje prudente como `posible accidente` o `posible anomalia visual`. Si no hay evidencia suficiente, la respuesta debe indicar `sin indicios visuales claros`.

## Modulo

La logica esta aislada en:

```text
src/vision/accident_detector.py
```

Funciones principales:

- `download_camera_image(image_url)`: descarga la imagen de una camara.
- `detect_objects(image_path_or_bytes)`: ejecuta deteccion de objetos.
- `classify_visual_risk(detections)`: aplica reglas heuristicas sobre las detecciones.
- `analyze_camera_image(image_url, camera_metadata=None)`: orquesta descarga, deteccion y clasificacion.

## Modelo

La implementacion usa Ultralytics si esta disponible:

```text
ultralytics
opencv-python
pillow
```

El modelo por defecto es `yolov8n.pt`, preentrenado para deteccion general de objetos. Se filtran estas clases:

- `car`
- `truck`
- `bus`
- `motorcycle`
- `person`
- `bicycle`

No se ha entrenado un detector especifico de accidentes porque no hay un dataset anotado propio del proyecto. Por eso la deteccion es preliminar y se basa en objetos visibles y reglas.

Si Ultralytics, Pillow o los pesos del modelo no estan disponibles, el backend devuelve una respuesta controlada con `model_status=unavailable` o `model_status=error`, sin romper el resto del sistema.

## Reglas Heuristicas

Con una sola imagen no se puede confirmar si un vehiculo esta detenido, si hay un bloqueo real de carril o si se ha producido un accidente. Por eso las reglas solo elevan el nivel de riesgo cuando hay senales visuales:

- personas cerca de vehiculos;
- acumulacion anormal de vehiculos;
- detecciones de vehiculos muy juntas;
- vehiculos grandes o cercanos que podrian bloquear parte de un carril;
- bicicletas junto a vehiculos.

Niveles de salida:

| Campo | Valores |
|---|---|
| `risk_level` | `bajo`, `medio`, `alto` |
| `label` | `sin_indicios`, `posible_anomalia`, `posible_accidente` |
| `confidence` | Valor aproximado entre `0.0` y `1.0` |

## Endpoints

### `POST /vision/analyze-camera`

Analiza una camara por `camera_id` o una imagen directa por `image_url`.

```json
{
  "camera_id": "77"
}
```

```json
{
  "image_url": "http://www.bizkaimove.com/camaras/cam1.jpg"
}
```

Respuesta:

```json
{
  "camera_id": "77",
  "camera_name": "CCTV 300 - Camara DOMO nudo Kukularra",
  "image_url": "http://...",
  "risk_level": "bajo",
  "label": "sin_indicios",
  "confidence": 0.12,
  "detections": [],
  "reason": "Sin indicios visuales claros de accidente o anomalia en esta imagen.",
  "timestamp": "2026-05-13T..."
}
```

### `GET /vision/analyze-sample`

Analiza una muestra de camaras con `image_url`.

```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/vision/analyze-sample?limit=5"
```

## Frontend

Streamlit incluye:

- boton `Analizar imagen con vision` dentro de la pestana `Camaras`;
- pestana `Vision` para seleccionar una camara con imagen o introducir una URL;
- visualizacion de nivel de riesgo, etiqueta, razon, objetos detectados e imagen original;
- advertencia visible: el analisis es preliminar y no confirma accidentes oficialmente.

## Chatbot

El chatbot detecta preguntas visuales como:

```text
Ves algun accidente en esta camara?
Analiza la camara 77
Analiza la camara de Bilbao
Hay anomalias visuales?
```

Si hay `camera_id`, municipio, carretera o URL, usa el analisis visual preliminar. Si no hay camara concreta, pide que se indique una camara, municipio, carretera o URL de imagen. Este flujo esta separado del RAG textual.

## Limitaciones

- Una sola imagen no permite confirmar accidentes.
- YOLO preentrenado detecta objetos generales, no accidentes como evento.
- La calidad depende de la imagen de la camara, resolucion, clima, oclusion y angulo.
- Puede haber falsos positivos y falsos negativos.
- No sustituye fuentes oficiales ni supervision humana.
- No se suben imagenes a APIs pagas; el analisis es local.

## Mejoras Futuras

- Crear dataset anotado de escenas de trafico locales.
- Fine-tuning de un detector especifico de incidentes.
- Analisis temporal de secuencias para distinguir vehiculos detenidos de vehiculos en movimiento.
- Segmentacion de carriles y zonas de calzada.
- Calibracion de umbrales por camara y carretera.
