# Frontend Visual

## Identidad

La interfaz Streamlit incorpora una identidad visual inspirada en la Universidad de Deusto, Bilbao y Euskadi. La paleta aplicada es:

| Uso | Color |
| --- | --- |
| Azul Deusto principal | `#003B7A` |
| Azul tecnológico secundario | `#2F80ED` |
| Verde Euskadi | `#00843D` |
| Rojo Bilbao/Euskadi | `#DA291C` |
| Blanco | `#FFFFFF` |
| Gris fondo | `#F4F6F8` |
| Gris texto | `#1F2933` |

## Cambios Realizados

- Navbar de pestañas y barra lateral con Azul Deusto.
- Hero superior para movilidad urbana inteligente en Euskadi, con fondo preparado para `assets/img/bilbao_map.jpg`.
- Hero con un único chip institucional: "Universidad de Deusto".
- Título principal del hero: "Chatbot de Movilidad Urbana".
- Tarjetas blancas con bordes redondeados, bordes suaves y sombra ligera para métricas, tablas, dataframes y expanders.
- Botones principales en Azul Deusto con estado hover en azul tecnológico.
- Verde Euskadi aplicado a estados positivos o normales, como pestaña activa y métricas.
- Rojo reservado para errores o alertas importantes mediante los estados de Streamlit.
- Espaciado, tipografía, títulos, inputs y layout responsive ajustados.
- Texto principal actualizado a: "Primera versión funcional para consultas sobre movilidad urbana de Euskadi."

## Orden De Secciones

El orden visual principal del frontend queda:

1. Chatbot
2. Incidencias
3. Cámaras
4. Congestión
5. Corpus multifuente
6. RAG

La sección de Visión por computador se mantiene al final para conservar funcionalidad existente.

## Assets

La carpeta `assets/img/` queda preparada con nombres de placeholder:

- `bilbao_map.jpg`
- `traffic_network.jpg`
- `urban_sensors.jpg`

El hero carga `bilbao_map.jpg` si está disponible. Si no existe o no se puede leer, usa un fondo visual CSS con la misma paleta para no romper la interfaz.

## Pruebas Realizadas

- Validación sintáctica de `frontend/app.py` con `ast.parse`: correcta.
- Comprobación de presencia de hero, paleta y nuevo texto: correcta.
- Comprobación de orden de pestañas mediante AST: correcta.
- Prueba funcional de carga con `streamlit.testing.v1.AppTest`: sin excepciones no controladas.
- Prueba local con servidores levantados: `http://127.0.0.1:8000/docs` respondió `200`, `http://127.0.0.1:8501` respondió `200` y `/corpus` devolvió `35` documentos.

Durante la prueba de carga pueden aparecer mensajes `st.error` si el backend local no está levantado, porque Streamlit ejecuta el contenido de todas las pestañas al renderizar. Ese comportamiento ya existía y no implica cambios en la lógica de endpoints.
