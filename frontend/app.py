import requests
import streamlit as st

from src.config import settings


st.set_page_config(page_title="Movilidad Urbana", layout="wide")

st.title("Chatbot Movilidad Urbana")
st.caption("Primera version funcional para consultar Trafikoa y probar RAG.")

api_url = st.sidebar.text_input("Backend URL", value=settings.backend_url)

tab_incidents, tab_cameras, tab_congestion, tab_rag = st.tabs(
    ["Incidencias", "Camaras", "Congestion", "RAG"]
)


def get_json(path: str, params: dict | None = None) -> dict:
    response = requests.get(f"{api_url}{path}", params=params, timeout=20)
    response.raise_for_status()
    return response.json()


with tab_incidents:
    st.subheader("Incidencias")
    if st.button("Descargar incidencias", use_container_width=True):
        try:
            payload = get_json("/incidents")
            st.metric("Total", payload["count"])
            st.dataframe(payload["items"], use_container_width=True)
        except requests.RequestException as exc:
            st.error(f"No se pudieron descargar las incidencias: {exc}")

with tab_cameras:
    st.subheader("Camaras")
    if st.button("Descargar camaras", use_container_width=True):
        try:
            payload = get_json("/cameras")
            st.metric("Total", payload["count"])
            st.dataframe(payload["items"], use_container_width=True)
        except requests.RequestException as exc:
            st.error(f"No se pudieron descargar las camaras: {exc}")

with tab_congestion:
    st.subheader("Nivel de congestion")
    speed = st.number_input("Velocidad media actual (km/h)", min_value=0.0, value=45.0)
    free_flow_speed = st.number_input(
        "Velocidad fluida esperada (km/h)",
        min_value=1.0,
        value=80.0,
    )
    incidents_count = st.number_input("Incidencias cercanas", min_value=0, value=0)

    if st.button("Calcular congestion", use_container_width=True):
        try:
            payload = get_json(
                "/congestion",
                params={
                    "speed_kmh": speed,
                    "free_flow_speed_kmh": free_flow_speed,
                    "incidents_count": incidents_count,
                },
            )
            st.success(f"Nivel estimado: {payload['level']}")
        except requests.RequestException as exc:
            st.error(f"No se pudo calcular la congestion: {exc}")

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
