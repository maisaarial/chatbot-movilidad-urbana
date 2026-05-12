from collections import Counter

import requests
import streamlit as st

from src.config import settings


st.set_page_config(page_title="Movilidad Urbana", layout="wide")

st.title("Chatbot Movilidad Urbana")
st.caption("Primera version funcional para consultar Trafikoa y probar RAG.")

api_url = st.sidebar.text_input("Backend URL", value=settings.backend_url)

tab_incidents, tab_cameras, tab_congestion, tab_chatbot, tab_corpus, tab_rag = st.tabs(
    ["Incidencias", "Camaras", "Congestion", "Chatbot", "Corpus multifuente", "RAG"]
)


def get_json(path: str, params: dict | None = None) -> dict:
    response = requests.get(f"{api_url}{path}", params=params, timeout=20)
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        detail = _extract_error_detail(response)
        raise requests.HTTPError(detail, response=response) from exc
    return response.json()


def post_json(path: str, payload: dict | None = None) -> dict:
    response = requests.post(f"{api_url}{path}", json=payload, timeout=240)
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


def _source_label(index: int, metadata: dict) -> str:
    parts = [
        metadata.get("document_type") or metadata.get("tipo") or "fuente",
        metadata.get("carretera"),
        metadata.get("tipo")
        if metadata.get("tipo") != metadata.get("document_type")
        else None,
        metadata.get("municipio"),
        metadata.get("timestamp"),
    ]
    clean_parts = [str(part) for part in parts if part]
    return f"{index}. {' | '.join(clean_parts)}"


def _source_summary(metadata: dict) -> dict:
    return {
        "carretera": _source_value(metadata, "carretera"),
        "tipo": _source_value(metadata, "tipo"),
        "causa": _source_value(metadata, "causa"),
        "sentido": _source_value(metadata, "sentido"),
        "municipio": _source_value(metadata, "municipio"),
        "provincia": _source_value(metadata, "provincia"),
        "timestamp": _source_value(metadata, "timestamp"),
        "congestion": _source_value(metadata, "congestion"),
        "valor_trafico": _source_value(metadata, "valor_trafico"),
        "unidad": _source_value(metadata, "unidad"),
        "nombre": _source_value(metadata, "nombre"),
        "image_url": _source_value(metadata, "image_url"),
        "maps_url": _source_value(metadata, "maps_url"),
    }


def _source_value(metadata: dict, key: str) -> str:
    value = metadata.get(key)
    if value is None or str(value).strip() == "":
        return "no disponible"
    return str(value)


def _maps_url_from_item(item: dict) -> str:
    if item.get("maps_url"):
        return str(item["maps_url"])
    latitude = item.get("latitude")
    longitude = item.get("longitude")
    if latitude is None or longitude is None:
        return ""
    if str(latitude).strip() == "" or str(longitude).strip() == "":
        return ""
    return f"https://www.google.com/maps?q={latitude},{longitude}"


def _sort_cameras_for_display(cameras: list[dict]) -> list[dict]:
    return sorted(
        cameras,
        key=lambda camera: (
            0 if camera.get("image_url") else 1,
            0 if _maps_url_from_item(camera) else 1,
            str(camera.get("carretera") or ""),
            str(camera.get("nombre") or ""),
        ),
    )


def _display_camera_results(cameras: list[dict]) -> None:
    sorted_cameras = _sort_cameras_for_display(cameras)
    st.dataframe(sorted_cameras, use_container_width=True, hide_index=True)
    for camera in sorted_cameras:
        title = " | ".join(
            str(value)
            for value in [
                camera.get("nombre"),
                camera.get("carretera"),
                camera.get("municipio"),
            ]
            if value
        )
        with st.expander(title or "Camara"):
            st.table(
                [
                    {
                        "id": camera.get("id", ""),
                        "nombre": camera.get("nombre", ""),
                        "carretera": camera.get("carretera", ""),
                        "municipio": camera.get("municipio", ""),
                        "provincia": camera.get("provincia", ""),
                        "image_url": camera.get("image_url", ""),
                        "source_url": camera.get("source_url", ""),
                    }
                ]
            )
            image_url = camera.get("image_url")
            if image_url:
                try:
                    st.image(image_url, use_container_width=True)
                except Exception as exc:
                    st.warning(f"No se pudo renderizar la imagen: {exc}")
                st.markdown(f"[Ver imagen original]({image_url})")
            else:
                st.info("No hay imagen disponible.")

            maps_url = _maps_url_from_item(camera)
            if maps_url:
                st.markdown(f"[Ver en Google Maps]({maps_url})")

            source_url = camera.get("source_url")
            if source_url:
                st.markdown(f"[Fuente original]({source_url})")


def _display_rag_status(status: dict) -> None:
    col_docs, col_age, col_ttl, col_state = st.columns(4)
    col_docs.metric("Documentos", status.get("documents_indexed", 0))
    age = status.get("age_seconds")
    col_age.metric("Edad", "n/d" if age is None else f"{int(age)} s")
    col_ttl.metric("TTL", f"{status.get('ttl_seconds', 0)} s")
    col_state.metric("Caducado", "si" if status.get("is_stale") else "no")

    details = {
        "estado": status.get("status"),
        "ultima_actualizacion": status.get("last_refresh_at"),
        "proxima_caducidad": status.get("expires_at"),
        "coleccion": status.get("collection"),
        "directorio": status.get("persist_dir"),
        "ultimo_error": status.get("last_error"),
    }
    st.table([details])


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

    st.markdown("**Buscar camaras procesadas**")
    search_col_q, search_col_city = st.columns(2)
    with search_col_q:
        camera_q = st.text_input("Texto libre", key="camera_search_q")
    with search_col_city:
        camera_city = st.text_input("Municipio", key="camera_search_city")

    search_col_road, search_col_province, search_col_limit = st.columns(3)
    with search_col_road:
        camera_road = st.text_input("Carretera", key="camera_search_road")
    with search_col_province:
        camera_province = st.text_input("Provincia", key="camera_search_province")
    with search_col_limit:
        camera_limit = st.number_input(
            "Limite",
            min_value=1,
            max_value=100,
            value=10,
            key="camera_search_limit",
        )
    camera_only_with_image = st.checkbox(
        "Mostrar solo camaras con imagen",
        value=True,
        key="camera_search_only_with_image",
    )

    if st.button("Buscar camaras", use_container_width=True):
        params = {
            "q": camera_q.strip() or None,
            "municipio": camera_city.strip() or None,
            "carretera": camera_road.strip() or None,
            "provincia": camera_province.strip() or None,
            "limit": camera_limit,
            "only_with_image": camera_only_with_image,
        }
        params = {
            key: value
            for key, value in params.items()
            if value is not None and value != ""
        }
        try:
            payload = get_json("/camaras/search", params=params)
            st.session_state["camera_search_results"] = payload["items"]
            st.success(f"Camaras encontradas: {payload['count']}")
        except requests.RequestException as exc:
            st.error(f"No se pudieron buscar camaras: {exc}")

    camera_search_results = st.session_state.get("camera_search_results", [])
    if camera_search_results:
        st.markdown("**Resultados de busqueda**")
        _display_camera_results(camera_search_results)

    if cameras:
        cameras = _sort_cameras_for_display(cameras)
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
            with st.expander(_source_label(index, metadata)):
                st.table([_source_summary(metadata)])
                st.markdown("**Texto recuperado**")
                st.write(source.get("text", ""))
                image_url = metadata.get("image_url")
                if image_url:
                    try:
                        st.image(image_url, use_container_width=True)
                    except Exception as exc:
                        st.warning(f"No se pudo renderizar la imagen: {exc}")
                    st.markdown(f"[Ver imagen original]({image_url})")
                elif metadata.get("document_type") == "camara":
                    st.info("No hay imagen disponible.")

                maps_url = _maps_url_from_item(metadata)
                if maps_url:
                    st.markdown(f"[Ver en Google Maps]({maps_url})")
                st.markdown("**Metadata completa**")
                st.json(metadata)

with tab_corpus:
    st.subheader("Corpus multifuente")
    if st.button("Actualizar corpus", use_container_width=True):
        try:
            payload = post_json("/corpus/refresh")
            st.session_state["corpus_items"] = payload.get("items", [])
            st.success(f"Corpus actualizado: {payload.get('count', 0)} documentos.")
        except requests.RequestException as exc:
            st.error(f"No se pudo actualizar el corpus: {exc}")

    try:
        if "corpus_items" not in st.session_state:
            payload = get_json("/corpus")
            st.session_state["corpus_items"] = payload.get("items", [])
    except requests.RequestException as exc:
        st.error(f"No se pudo cargar el corpus: {exc}")

    corpus_items = st.session_state.get("corpus_items", [])
    st.metric("Documentos", len(corpus_items))

    if corpus_items:
        source_counts = Counter(item.get("source", "") for item in corpus_items)
        st.markdown("**Conteo por fuente**")
        st.table(
            [
                {"source": source, "count": count}
                for source, count in sorted(source_counts.items())
            ]
        )

        known_sources = {"Ayuntamiento de Bilbao", "DEIA", "Bluesky"}
        sources = sorted(
            known_sources
            | {item.get("source", "") for item in corpus_items if item.get("source")}
        )
        municipios = sorted(
            {item.get("municipio", "") for item in corpus_items if item.get("municipio")}
        )
        event_types = sorted(
            {item.get("tipo_evento", "") for item in corpus_items if item.get("tipo_evento")}
        )

        col_source, col_municipio, col_event = st.columns(3)
        with col_source:
            selected_source = st.selectbox("Fuente", ["Todas"] + sources)
        with col_municipio:
            selected_municipio = st.selectbox("Municipio", ["Todos"] + municipios)
        with col_event:
            selected_event = st.selectbox("Tipo de evento", ["Todos"] + event_types)

        filtered_corpus = corpus_items
        if selected_source != "Todas":
            filtered_corpus = [
                item for item in filtered_corpus if item.get("source") == selected_source
            ]
        if selected_municipio != "Todos":
            filtered_corpus = [
                item for item in filtered_corpus if item.get("municipio") == selected_municipio
            ]
        if selected_event != "Todos":
            filtered_corpus = [
                item for item in filtered_corpus if item.get("tipo_evento") == selected_event
            ]

        st.dataframe(filtered_corpus, use_container_width=True, hide_index=True)
    else:
        st.info("Pulsa el boton para construir el corpus multifuente.")

with tab_rag:
    st.subheader("Estado RAG")
    if st.button("Actualizar indice RAG ahora", use_container_width=True):
        try:
            st.session_state["rag_status"] = post_json("/rag/refresh")
            st.success("Indice RAG actualizado.")
        except requests.RequestException as exc:
            st.error(f"No se pudo actualizar el indice RAG: {exc}")

    try:
        rag_status = st.session_state.get("rag_status") or get_json("/rag/status")
        _display_rag_status(rag_status)
    except requests.RequestException as exc:
        st.error(f"No se pudo obtener el estado RAG: {exc}")

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
