# API De Trafikoa/Open Data Euskadi

## Fuente Oficial

La API usada es la API oficial de trafico de Open Data Euskadi:

```text
https://api.euskadi.eus/traffic/v1.0
```

Documentacion publica:

```text
https://opendata.euskadi.eus/api-traffic/?api=traffic
```

## Endpoints Oficiales Usados

| Uso | Endpoint |
|---|---|
| Fuentes | `/sources` |
| Incidencias por fecha | `/incidences/byDate/{year}/{month}/{day}` |
| Camaras | `/cameras` |
| Flujos por fecha | `/flows/byDate/{year}/{month}/{day}` |
| Flujos por fecha y fuente | `/flows/byDate/{year}/{month}/{day}/bySource/{sourceId}` |
| Medidores | `/meters` |
| Medidores por fuente | `/meters/bySource/{sourceId}` |
| Niveles de servicio | `/levelOfService` |

## Incidencias

El modulo `src/trafikoa/incidents.py` usa:

```text
/incidences/byDate/{year}/{month}/{day}
```

La respuesta incluye campos como:

| Campo original | Campo normalizado |
|---|---|
| `startDate` | `timestamp` |
| `incidenceType` | `tipo` |
| `road` | `carretera` |
| `cause` | `causa` |
| `direction` | `sentido` |
| `cityTown` | `municipio` |
| `province` | `provincia` |
| `sourceId` | `fuente` |

Archivos generados:

```text
data/raw/incidents_raw.json
data/processed/incidents.csv
```

## Camaras

El modulo `src/trafikoa/cameras.py` usa:

```text
/cameras
```

La respuesta incluye campos como:

| Campo original | Campo normalizado |
|---|---|
| `cameraId` | `id` |
| `cameraName` | `nombre` |
| `road` | `carretera` |
| `address` o `cityTown` | `municipio` |
| `sourceId` | `provincia` aproximada por fuente cuando no viene provincia |
| `latitude` | `latitude` |
| `longitude` | `longitude` |
| `urlImage` | `image_url` |

Algunas camaras tienen coordenadas en grados decimales y otras en UTM. El modulo intenta normalizar coordenadas UTM a WGS84 cuando detecta valores fuera del rango normal de latitud/longitud.

Archivos generados:

```text
data/raw/cameras_raw.json
data/processed/cameras.csv
```

### Busqueda Estructurada De Camaras

El modulo `src/trafikoa/camera_search.py` no consulta de nuevo la API externa. Lee solamente:

```text
data/processed/cameras.csv
```

Esto permite responder rapido a consultas como:

```text
Muestrame camaras en Bilbao
Que camaras hay en la A-8
Hay camara en la BI-637
Camaras en Bizkaia
```

La busqueda es tolerante a mayusculas, minusculas y tildes. Puede filtrar por:

| Parametro | Campo consultado |
|---|---|
| `q` | `nombre`, `carretera`, `municipio`, `provincia` |
| `municipio` | `municipio` |
| `carretera` | `carretera` |
| `provincia` | `provincia` |
| `limit` | Numero maximo de resultados |

Endpoint local:

```text
GET /camaras/search
```

Ejemplos:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/camaras/search?q=Bilbao"
Invoke-RestMethod "http://127.0.0.1:8000/camaras/search?carretera=A-8"
Invoke-RestMethod "http://127.0.0.1:8000/camaras/search?provincia=BIZKAIA"
```

Cada camara incluye `maps_url` calculado a partir de `latitude` y `longitude` cuando ambos datos existen. No se inventan camaras ni coordenadas.

## Flows, Meters Y Level Of Service

Para congestion se usan mediciones reales de `flows`.

Endpoint principal:

```text
/flows/byDate/{year}/{month}/{day}/bySource/{sourceId}
```

Campos relevantes:

| Campo | Uso |
|---|---|
| `meterId` | Identifica el medidor. |
| `sourceId` | Identifica la fuente. |
| `meterDate` | Fecha de la medicion. |
| `timeRank` | Intervalo temporal. |
| `totalVehicles` | Variable principal para congestion. |
| `speedAvg` | Velocidad media, disponible solo en algunas fuentes. |
| `occupancy` | Ocupacion, disponible solo en algunas respuestas. |
| `levelOfService` | Nivel de servicio, no siempre viene informado en cada flow. |

Para metadatos de medidores:

```text
/meters/bySource/{sourceId}
```

Se usan campos como:

| Campo | Uso |
|---|---|
| `meterId` | Union con flows. |
| `meterCode` | Identificador auxiliar. |
| `municipality` | Municipio. |
| `province` | Provincia. |
| `description`, `system`, `etd` | Nombre descriptivo cuando existe. |

Para catalogo de niveles:

```text
/levelOfService
```

Devuelve niveles como verde, amarillo y rojo. En esta fase se documentan y se contempla su uso, pero el calculo principal se basa en `totalVehicles` porque es la medicion mas estable en las respuestas probadas.

Archivos generados:

```text
data/raw/congestion_raw.json
data/processed/congestion.csv
```

## Limitaciones Detectadas

| Limitacion | Impacto |
|---|---|
| `/flows` sin fecha devuelve 404. | Hay que consultar flows con fecha. |
| Los flows pueden tener muchas paginas. | Se usa `max_pages` para limitar la descarga inicial. |
| Algunas fuentes devuelven `speedAvg`, otras no. | La primera version usa `totalVehicles`. |
| `levelOfService` no siempre aparece en cada flow. | No se puede depender de ese campo para todos los registros. |
| Algunos medidores no traen nombre de carretera. | Se usa un identificador real `medidor:<codigo>` para no inventar datos. |
| Algunas camaras no tienen `image_url`. | El frontend solo permite visualizar camaras que si tienen imagen. |
| Algunas coordenadas de camaras vienen en UTM. | Se normalizan cuando se detectan. |

No se generan datos inventados. Cuando falta informacion descriptiva, se conserva el dato real disponible.
