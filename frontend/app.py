from collections import Counter

import requests
import streamlit as st

from src.config import settings


st.set_page_config(page_title="Movilidad Urbana", layout="wide")

st.title("Chatbot Movilidad Urbana")
st.caption("Primera version funcional para consultar Trafikoa y probar RAG.")

api_url = st.sidebar.text_input("Backend URL", value=settings.backend_url)

tab_incidents, tab_cameras, tab_congestion, tab_chatbot, tab_rag = st.tabs(
    ["Incidencias", "Camaras", "Congestion", "Chatbot", "RAG"]
)


def get_json(path: str, params: dict | None = None) -> dict:
    response = requests.get(f"{api_url}{path}", params=params, timeout=20)
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        detail = _extract_error_detail(response)
        raise requests.HTTPError(detail, response=response) from exc
    return response.json()


def post_json(path: str, payload: dict) -> dict:
    response = requests.post(f"{api_url}{path}", json=payload, timeout=180)
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        detail = _extract_error_detail(response)
        raise requests.HTTPError(detail, response=response) from exc
    return response.json()


def _extract_error_detail(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text or str(response.status_code)
    return str(payload.get("detail") or payload)


with tab_incidents:
    st.subheader("Incidencias")
    if st.button("Descargar incidencias", use_container_width=True):
        try:
            payload = get_json("/incidencias")
            st.session_state["incidents"] = payload["items"]
        except requests.RequestException as exc:
            st.error(f"No se pudieron descargar las incidencias: {exc}")

    incidents = st.session_state.get("incidents", [])
    st.metric("Total", len(incidents))
    if incidents:
        st.dataframe(incidents, use_container_width=True, hide_index=True)
    else:
        st.info("Pulsa el boton para descargar incidencias reales desde Trafikoa.")

with tab_cameras:
    st.subheader("Camaras")
    if st.button("Descargar camaras", use_container_width=True):
        try:
            payload = get_json("/camaras")
            st.session_state["cameras"] = payload["items"]
        except requests.RequestException as exc:
            st.error(f"No se pudieron descargar las camaras: {exc}")

    cameras = st.session_state.get("cameras", [])
    st.metric("Total", len(cameras))
    if cameras:
        st.dataframe(cameras, use_container_width=True, hide_index=True)

        cameras_with_image = [camera for camera in cameras if camera.get("image_url")]
        if cameras_with_image:
            labels = [
                f"{camera.get('id', '')} - {camera.get('nombre', '')}"
                for camera in cameras_with_image
            ]
            selected_label = st.selectbox("Camara con imagen", labels)
            selected_camera = cameras_with_image[labels.index(selected_label)]
            st.image(
                selected_camera["image_url"],
                caption=selected_camera.get("nombre", ""),
                use_container_width=True,
            )
        else:
            st.info("No se han encontrado camaras con image_url.")
    else:
        st.info("Pulsa el boton para descargar camaras reales desde Trafikoa.")

with tab_congestion:
    st.subheader("Congestion")
    col_low, col_high, col_pages = st.columns(3)
    with col_low:
        umbral_bajo = st.number_input("Umbral bajo", min_value=0.0, value=50.0)
    with col_high:
        umbral_alto = st.number_input("Umbral alto", min_value=1.0, value=150.0)
    with col_pages:
        max_pages = st.number_input("Paginas flows", min_value=1, max_value=500, value=25)

    if st.button("Descargar congestion", use_container_width=True):
        try:
            payload = get_json(
                "/congestion",
                params={
                    "umbral_bajo": umbral_bajo,
                    "umbral_alto": umbral_alto,
                    "max_pages": max_pages,
                },
            )
            st.session_state["congestion"] = payload["items"]
        except requests.RequestException as exc:
            st.error(f"No se pudo descargar la congestion: {exc}")

    congestion_rows = st.session_state.get("congestion", [])
    st.metric("Registros", len(congestion_rows))

    if congestion_rows:
        roads = sorted({row.get("carretera", "") for row in congestion_rows if row.get("carretera")})
        levels = ["baja", "media", "alta"]

        col_road, col_level = st.columns(2)
        with col_road:
            selected_road = st.selectbox("Carretera", ["Todas"] + roads)
        with col_level:
            selected_level = st.selectbox("Nivel", ["Todos"] + levels)

        filtered_rows = congestion_rows
        if selected_road != "Todas":
            filtered_rows = [
                row for row in filtered_rows if row.get("carretera") == selected_road
            ]
        if selected_level != "Todos":
            filtered_rows = [
                row for row in filtered_rows if row.get("congestion") == selected_level
            ]

        counts = Counter(row.get("congestion", "") for row in filtered_rows)
        low_col, medium_col, high_col = st.columns(3)
        low_col.metric("Baja", counts.get("baja", 0))
        medium_col.metric("Media", counts.get("media", 0))
        high_col.metric("Alta", counts.get("alta", 0))

        st.dataframe(filtered_rows, use_container_width=True, hide_index=True)
    else:
        st.info("Pulsa el boton para descargar mediciones reales de Trafikoa.")

with tab_chatbot:
    st.subheader("Chatbot RAG")
    question = st.text_input(
        "Pregunta",
        placeholder="Ej. Hay congestion en Bilbao? Hay camaras con imagen?",
    )
    if st.button("Preguntar", use_container_width=True):
        try:
            payload = post_json("/chat", {"question": question})
            st.session_state["chat_answer"] = payload.get("answer", "")
            st.session_state["chat_sources"] = payload.get("sources", [])
        except requests.RequestException as exc:
            st.error(f"No se pudo ejecutar el chatbot: {exc}")

    answer = st.session_state.get("chat_answer")
    sources = st.session_state.get("chat_sources", [])
    if answer:
        st.markdown("**Respuesta**")
        st.write(answer)

    if sources:
        st.markdown("**Fuentes usadas**")
        for index, source in enumerate(sources, start=1):
            metadata = source.get("metadata", {})
            label = metadata.get("document_type") or metadata.get("tipo") or f"Fuente {index}"
            with st.expander(f"{index}. {label}"):
                st.write(source.get("text", ""))
                st.json(metadata)
                image_url = metadata.get("image_url")
                if image_url:
                    if image_url.startswith("http://"):
                        st.markdown(f"[Abrir imagen]({image_url})")
                    else:
                        st.image(image_url, use_container_width=True)

with tab_rag:
    st.subheader("Busqueda RAG basica")
    documents = st.text_area(
        "Documentos para indexar",
        placeholder="Un documento por linea. Ej: La A-8 presenta retenciones...",
    )
    if st.button("Indexar documentos", use_container_width=True):
        items = [line.strip() for line in documents.splitlines() if line.strip()]
        try:
            response = requests.post(f"{api_url}/rag/documents", json=items, timeout=20)
            response.raise_for_status()
            st.success(f"Documentos indexados: {response.json()['count']}")
        except requests.RequestException as exc:
            st.error(f"No se pudieron indexar documentos: {exc}")

    query = st.text_input("Consulta")
    if st.button("Buscar", use_container_width=True):
        try:
            payload = get_json("/rag/search", params={"query": query})
            st.dataframe(payload["results"], use_container_width=True)
        except requests.RequestException as exc:
            st.error(f"No se pudo ejecutar la busqueda: {exc}")
