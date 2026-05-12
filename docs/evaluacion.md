# Evaluacion Del Sistema

## Objetivo

La evaluacion se plantea como una evaluacion aplicada y reproducible para un chatbot RAG multifuente sin datos anotados publicos. En lugar de hacer fine-tuning o crear un dataset grande artificial, se usa una muestra pequena anotada manualmente que permite medir el sistema por componentes y detectar fallos concretos.

La muestra inicial esta en:

```text
data/evaluation/eval_queries.csv
```

Contiene 25 preguntas con estas columnas:

| Columna | Uso |
|---|---|
| `id` | Identificador de la pregunta. |
| `question` | Pregunta en lenguaje natural. |
| `expected_intent` | Intencion esperada de alto nivel. |
| `expected_entities` | Entidades esperadas anotadas manualmente. |
| `expected_source_type` | Tipo de fuente esperado. |
| `expected_source` | Fuente esperada. |
| `expected_answer_contains` | Terminos que deberian aparecer en la respuesta. |
| `notes` | Observaciones de anotacion. |

La muestra cubre incidencias Trafikoa, camaras, congestion, avisos del Ayuntamiento de Bilbao, DEIA - Bizkaimove, Bluesky y preguntas sin informacion suficiente.

## Por Que Una Muestra Pequena

No existe un corpus anotado especifico para este dominio y estas fuentes. Por eso se usa una muestra pequena, revisable y ampliable, con anotacion manual. Esta decision es defendible porque:

- permite evaluar el sistema real con preguntas representativas;
- no introduce datos inventados ni respuestas generadas como verdad absoluta;
- separa errores de retrieval, errores de respuesta y ausencia real de evidencia;
- deja una base extensible para futuras iteraciones.

## Evaluacion Por Componentes

La evaluacion se divide en dos scripts:

```powershell
.venv\Scripts\python scripts\evaluate_retrieval.py
.venv\Scripts\python scripts\evaluate_chatbot.py
```

### Retrieval

`scripts/evaluate_retrieval.py` ejecuta `retrieve(question, k=5)` para cada pregunta y guarda:

```text
data/evaluation/retrieval_results.csv
```

Metricas:

| Metrica | Interpretacion |
|---|---|
| `Recall@k` aproximado | Porcentaje de preguntas donde aparece la fuente o tipo esperado en el top-k. |
| `MRR@k` aproximado | Premia que la fuente esperada aparezca en posiciones altas. |
| `source_rank` | Primera posicion donde aparece la fuente esperada. |
| `source_type_rank` | Primera posicion donde aparece el tipo de fuente esperado. |

Resultado de referencia:

```text
retrieval_queries=25
metric_applicable=23
recall@5=0.652
mrr@5=0.630
```

Las preguntas `no_evidence` no se incluyen en el denominador automatico de Recall/MRR porque no tienen fuente esperada.

### Chatbot Final

`scripts/evaluate_chatbot.py` usa por defecto `src.rag.chatbot.answer_question()`. Tambien puede usar el endpoint:

```powershell
.venv\Scripts\python scripts\evaluate_chatbot.py --mode endpoint --endpoint http://127.0.0.1:8000/chat
```

Guarda:

```text
data/evaluation/chatbot_results.csv
```

Comprueba:

- respuesta generada;
- fuentes usadas;
- si aparece la fuente esperada;
- si la respuesta contiene los terminos anotados en `expected_answer_contains`.

Resultado de referencia:

```text
chatbot_queries=25
completed=25
contains_expected_rate=0.840
expected_source_rate=0.800
```

## Intent Y Entidades

La columna `expected_intent` permite una evaluacion futura de clasificacion de intencion. Actualmente no hay un clasificador separado; la intencion se resuelve de forma implicita mediante reglas, busqueda estructurada de camaras y retrieval.

La columna `expected_entities` sirve como validacion manual. Por ejemplo:

- `carretera=A-8`
- `municipio=Bilbao`
- `source=Bizkaimove`
- `tipo=paso_alternativo`

En una fase posterior se podria medir extraccion de entidades con precision/recall, pero ahora se usa para revisar casos concretos sin sobredimensionar el proyecto.

## Evaluacion Humana

Ademas de las comprobaciones automaticas, la respuesta final del chatbot debe evaluarse manualmente con escala 1-5:

| Criterio | Pregunta guia |
|---|---|
| Relevancia | Responde a la pregunta planteada? |
| Fidelidad | Esta apoyada solo en las fuentes recuperadas? |
| Claridad | Es comprensible y concreta? |
| Utilidad | Ayuda a tomar una decision o entender la situacion? |

Esta evaluacion humana es importante porque una respuesta puede contener las palabras esperadas y aun asi ser poco util, incompleta o confusa.

## Limitaciones

- La muestra de 25 preguntas es pequena y no pretende ser estadisticamente representativa.
- Las fuentes son vivas: Trafikoa, Bizkaimove, Bilbao y Bluesky cambian con el tiempo.
- Algunas preguntas ambiguas pueden recuperar una fuente plausible pero no la fuente anotada.
- Las camaras se resuelven por busqueda estructurada antes del RAG; por eso la evaluacion de retrieval semantico no representa completamente ese flujo.
- Bluesky depende de las cuentas seguidas y de la actividad reciente del timeline.
- `expected_answer_contains` es una comprobacion de terminos, no una evaluacion semantica completa.
- Las preguntas sin informacion suficiente requieren revision humana, porque el retrieval puede recuperar documentos cercanos aunque no respondan realmente.

## Resultados Interpretados

Los resultados iniciales muestran que el sistema ya recupera y cita fuentes multifuente, pero tambien revelan areas de mejora:

- consultas de camaras funcionan mejor en el chatbot final que en retrieval puro, porque usan busqueda estructurada;
- algunas consultas de congestion se confunden con incidencias si comparten entidades como Bilbao;
- una consulta social amplia sobre Bizkaia puede recuperar avisos institucionales antes que Bluesky;
- las preguntas fuera de alcance deben revisarse para evitar respuestas con evidencia insuficiente.

La evaluacion, por tanto, no es solo una nota final: es una herramienta para priorizar mejoras reales del sistema.
