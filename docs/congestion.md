# Calculo De Congestion

## Objetivo

El modulo de congestion clasifica mediciones de trafico como:

- `baja`
- `media`
- `alta`

La primera version funcional usa datos reales de Trafikoa, pero aplica una regla sencilla de umbrales. Esto permite tener un comportamiento explicable y defendible antes de introducir modelos mas complejos.

## Variable Usada

La variable principal es:

```text
totalVehicles
```

Esta variable procede de los endpoints `flows` de Trafikoa.

## Unidad

La unidad usada en los registros procesados es:

```text
vehiculos/intervalo
```

Esto significa que el valor representa el numero de vehiculos registrados en el intervalo temporal indicado por `timeRank`.

## Regla De Umbrales

La funcion general esta en `src/congestion.py`:

```python
calcular_congestion(valor, umbral_bajo, umbral_alto)
```

Regla:

| Condicion | Resultado |
|---|---|
| `valor < umbral_bajo` | `baja` |
| `umbral_bajo <= valor < umbral_alto` | `media` |
| `valor >= umbral_alto` | `alta` |

Los umbrales por defecto estan en `src/config.py` y pueden configurarse desde `.env`:

```text
CONGESTION_LOW_THRESHOLD=50
CONGESTION_HIGH_THRESHOLD=150
```

## Ejemplo

Con:

```text
umbral_bajo = 50
umbral_alto = 150
```

La clasificacion seria:

| Valor | Congestion |
|---:|---|
| `10` | `baja` |
| `50` | `media` |
| `86` | `media` |
| `150` | `alta` |
| `210` | `alta` |

Ejemplo de comando:

```powershell
curl.exe "http://127.0.0.1:8000/congestion?valor=151&umbral_bajo=50&umbral_alto=150"
```

Respuesta esperada:

```json
{"level":"alta"}
```

## Justificacion

Esta solucion es una primera aproximacion por umbrales. Se eligio porque:

- Usa datos reales de Trafikoa.
- Es interpretable.
- Es facil de explicar en clase.
- Permite configurar los umbrales.
- Evita inventar velocidades, ocupaciones o niveles de servicio cuando no vienen en la respuesta.

La API tambien expone `speedAvg`, `occupancy` y `levelOfService`, pero no siempre aparecen en todos los registros probados. Por eso la primera version usa `totalVehicles`, que aparece de forma estable en los flows consultados.

## Generacion Del CSV

El modulo `src/trafikoa/congestion.py` guarda los resultados en:

```text
data/processed/congestion.csv
```

Columnas:

| Columna | Significado |
|---|---|
| `timestamp` | Fecha y hora/intervalo de la medicion. |
| `carretera` | Nombre o identificador real del medidor. |
| `municipio` | Municipio asociado al medidor si esta disponible. |
| `provincia` | Provincia asociada al medidor si esta disponible. |
| `valor_trafico` | Valor usado para clasificar. |
| `unidad` | Unidad del valor. |
| `congestion` | Nivel baja, media o alta. |
| `fuente` | Fuente oficial del dato. |
| `rag_text` | Texto preparado para futura indexacion RAG. |

## Preparacion Para RAG

Cada fila incluye `rag_text`, que convierte el registro estructurado en una frase natural.

Ejemplo:

```text
Congestion media en medidor:248, Bilbao, Bizkaia. Valor de trafico: 86.0 vehiculos/intervalo. Fecha: 2026-05-11T08:25. Fuente: Ayuntamiento Bilbao.
```

Este campo se podra enviar posteriormente al endpoint:

```text
POST /rag/documents
```

De este modo, el chatbot podra responder preguntas sobre congestion usando busqueda semantica.
