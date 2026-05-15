import base64
from collections import Counter
from pathlib import Path

import requests
import streamlit as st

from src.config import settings


ASSETS_IMG_DIR = Path(__file__).resolve().parents[1] / "assets" / "img"
HERO_IMAGE_PATH = ASSETS_IMG_DIR / "bilbao_map.jpg"


st.set_page_config(page_title="Movilidad Urbana", layout="wide")

def _asset_data_uri(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""

    suffix = path.suffix.lower()
    mime_type = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
    try:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    except OSError:
        return ""
    return f"data:{mime_type};base64,{encoded}"


def _hero_background_css() -> str:
    overlay = (
        "linear-gradient(120deg, rgba(0, 59, 122, 0.94), "
        "rgba(0, 59, 122, 0.76) 48%, rgba(0, 132, 61, 0.68))"
    )
    hero_image = _asset_data_uri(HERO_IMAGE_PATH)
    if hero_image:
        return f"background-image: {overlay}, url('{hero_image}');"
    return f"background: {overlay};"


def _render_theme() -> None:
    hero_background = _hero_background_css()
    st.markdown(
        f"""
        <style>
        :root {{
            --deusto-blue: #003B7A;
            --tech-blue: #2F80ED;
            --euskadi-green: #00843D;
            --bilbao-red: #DA291C;
            --surface: #FFFFFF;
            --background: #F4F6F8;
            --text: #1F2933;
            --border: rgba(31, 41, 51, 0.10);
            --shadow: 0 14px 32px rgba(0, 59, 122, 0.11);
        }}

        html,
        body {{
            background: #001B3A;
        }}

        .stApp {{
            background:
                radial-gradient(circle at 11% 25%, rgba(255,255,255,0.34) 0 2px, rgba(0,132,61,0.30) 3px 5px, transparent 6px),
                radial-gradient(circle at 24% 67%, rgba(255,255,255,0.26) 0 2px, rgba(47,128,237,0.28) 3px 5px, transparent 6px),
                radial-gradient(circle at 56% 20%, rgba(255,255,255,0.26) 0 2px, rgba(0,132,61,0.26) 3px 5px, transparent 6px),
                radial-gradient(circle at 74% 58%, rgba(255,255,255,0.28) 0 2px, rgba(47,128,237,0.30) 3px 5px, transparent 6px),
                linear-gradient(24deg, transparent 18%, rgba(255,255,255,0.08) 18.12%, transparent 31%),
                linear-gradient(145deg, transparent 58%, rgba(255,255,255,0.07) 58.12%, transparent 72%),
                linear-gradient(90deg, rgba(255,255,255,0.055) 1px, transparent 1px),
                linear-gradient(0deg, rgba(255,255,255,0.055) 1px, transparent 1px),
                radial-gradient(circle at 12% 18%, rgba(47, 128, 237, 0.24), transparent 30rem),
                radial-gradient(circle at 88% 10%, rgba(0, 132, 61, 0.24), transparent 28rem),
                radial-gradient(circle at 76% 82%, rgba(47, 128, 237, 0.16), transparent 34rem),
                linear-gradient(135deg, #001B3A 0%, var(--deusto-blue) 46%, #006B59 100%);
            background-size:
                auto,
                auto,
                auto,
                auto,
                auto,
                auto,
                72px 72px,
                72px 72px,
                auto,
                auto,
                auto,
                auto;
            background-attachment: fixed;
            color: var(--text);
        }}

        [data-testid="stAppViewContainer"] {{
            background: transparent;
            color: var(--text);
        }}

        [data-testid="stHeader"] {{
            background: rgba(0, 35, 73, 0.60);
            border-bottom: 1px solid rgba(255, 255, 255, 0.14);
            backdrop-filter: blur(14px);
        }}

        .block-container {{
            width: 100%;
            max-width: 1180px;
            margin-left: auto;
            margin-right: auto;
            padding-top: 1.5rem;
            padding-left: 2rem;
            padding-right: 2rem;
            padding-bottom: 3rem;
        }}

        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, var(--deusto-blue), #062F60);
        }}

        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span {{
            color: #FFFFFF;
        }}

        [data-testid="stSidebar"] input {{
            background: #FFFFFF;
            color: var(--text);
            border-radius: 8px;
        }}

        .deusto-hero {{
            {hero_background}
            position: relative;
            overflow: hidden;
            min-height: 288px;
            border-radius: 8px;
            padding: clamp(1.75rem, 4vw, 3.2rem);
            color: #FFFFFF;
            background-size: cover;
            background-position: center;
            border: 1px solid rgba(255, 255, 255, 0.24);
            box-shadow: var(--shadow);
            margin-bottom: 1.4rem;
        }}

        .deusto-hero::after {{
            content: "";
            position: absolute;
            inset: 0;
            background-image:
                linear-gradient(90deg, rgba(255,255,255,0.08) 1px, transparent 1px),
                linear-gradient(0deg, rgba(255,255,255,0.08) 1px, transparent 1px);
            background-size: 56px 56px;
            opacity: 0.34;
            pointer-events: none;
        }}

        .deusto-hero > * {{
            position: relative;
            z-index: 1;
        }}

        .hero-badges {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
            margin-bottom: 1.15rem;
        }}

        .hero-badge {{
            border: 1px solid rgba(255, 255, 255, 0.38);
            background: rgba(255, 255, 255, 0.13);
            border-radius: 999px;
            padding: 0.32rem 0.72rem;
            font-size: 0.82rem;
            font-weight: 700;
        }}

        .deusto-hero h1 {{
            margin: 0;
            color: #FFFFFF;
            font-size: clamp(2.05rem, 4.2vw, 4rem);
            line-height: 1.02;
            letter-spacing: 0;
        }}

        .deusto-hero p {{
            margin: 1rem 0 0;
            max-width: 760px;
            color: rgba(255, 255, 255, 0.92);
            font-size: clamp(1rem, 1.6vw, 1.18rem);
            line-height: 1.55;
        }}

        h1, h2, h3 {{
            color: var(--deusto-blue);
            letter-spacing: 0;
        }}

        h2, h3 {{
            margin-top: 0.55rem;
        }}

        div[data-testid="stTabs"] [data-baseweb="tab-list"] {{
            gap: 0.25rem;
            background: var(--deusto-blue);
            border-radius: 8px;
            padding: 0.38rem;
            box-shadow: 0 10px 24px rgba(0, 59, 122, 0.16);
        }}

        div[data-testid="stTabs"] [data-baseweb="tab"] {{
            height: 2.65rem;
            border-radius: 6px;
            color: #FFFFFF;
            font-weight: 700;
            padding: 0 1rem;
        }}

        div[data-testid="stTabs"] [aria-selected="true"] {{
            background: #FFFFFF;
            color: var(--deusto-blue);
            box-shadow: inset 0 -3px 0 var(--euskadi-green);
        }}

        div[data-testid="stTabs"] [data-baseweb="tab-panel"] {{
            margin-top: 1rem;
            padding: 1.2rem 1.1rem 1.45rem;
            background: rgba(255, 255, 255, 0.94);
            border: 1px solid rgba(255, 255, 255, 0.70);
            border-radius: 8px;
            box-shadow: var(--shadow);
            backdrop-filter: blur(10px);
        }}

        .stButton > button {{
            border: 0;
            border-radius: 8px;
            background: var(--deusto-blue);
            color: #FFFFFF;
            font-weight: 700;
            min-height: 2.65rem;
            box-shadow: 0 8px 18px rgba(0, 59, 122, 0.18);
            transition: background 160ms ease, transform 160ms ease, box-shadow 160ms ease;
        }}

        .stButton > button:hover {{
            background: var(--tech-blue);
            color: #FFFFFF;
            transform: translateY(-1px);
            box-shadow: 0 11px 22px rgba(47, 128, 237, 0.22);
        }}

        .stButton > button:active {{
            background: #002B5B;
            transform: translateY(0);
        }}

        div[data-testid="stMetric"],
        div[data-testid="stDataFrame"],
        div[data-testid="stTable"],
        div[data-testid="stExpander"] {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            box-shadow: var(--shadow);
        }}

        div[data-testid="stMetric"] {{
            border-left: 4px solid var(--euskadi-green);
            padding: 1rem;
        }}

        [data-testid="stAlert"] {{
            border-radius: 8px;
            box-shadow: 0 8px 22px rgba(31, 41, 51, 0.08);
        }}

        [data-testid="stTextInput"] input,
        [data-testid="stTextArea"] textarea,
        [data-testid="stNumberInput"] input,
        [data-baseweb="select"] > div {{
            border-radius: 8px;
            border-color: rgba(0, 59, 122, 0.20);
        }}

        input[type="checkbox"] {{
            accent-color: var(--euskadi-green);
        }}

        a {{
            color: var(--tech-blue);
            font-weight: 700;
        }}

        hr {{
            border-color: var(--border);
        }}

        @media (max-width: 768px) {{
            .block-container {{
                padding-left: 1rem;
                padding-right: 1rem;
            }}

            .deusto-hero {{
                min-height: 240px;
                padding: 1.45rem;
            }}

            div[data-testid="stTabs"] [data-baseweb="tab-list"] {{
                overflow-x: auto;
                justify-content: flex-start;
            }}

            div[data-testid="stTabs"] [data-baseweb="tab"] {{
                min-width: max-content;
                padding: 0 0.78rem;
            }}

            div[data-testid="stTabs"] [data-baseweb="tab-panel"] {{
                padding: 1rem 0.85rem 1.2rem;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_hero() -> None:
    st.markdown(
        """
        <section class="deusto-hero" aria-label="Movilidad urbana inteligente en Euskadi">
            <div class="hero-badges">
                <span class="hero-badge">Universidad de Deusto</span>
            </div>
            <h1>Chatbot de Movilidad Urbana</h1>
            <p>Primera versión funcional para consultas sobre movilidad urbana de Euskadi.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )


_render_theme()
_render_hero()

api_url = st.sidebar.text_input("Backend URL", value=settings.backend_url)

(
    tab_chatbot,
    tab_incidents,
    tab_cameras,
    tab_congestion,
    tab_corpus,
    tab_rag,
    tab_vision,
) = st.tabs(
    [
        "Chatbot",
        "Incidencias",
        "Cámaras",
        "Congestión",
        "Corpus multifuente",
        "RAG",
        "Visión",
    ]
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
        metadata.get("source"),
        metadata.get("source_type"),
        metadata.get("document_type") or metadata.get("tipo") or "fuente",
        metadata.get("title"),
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
        "source": _source_value(metadata, "source"),
        "source_type": _source_value(metadata, "source_type"),
        "title": _source_value(metadata, "title"),
        "url": _source_value(metadata, "url"),
        "tipo_evento": _source_value(metadata, "tipo_evento"),
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
    cameras_with_image = [camera for camera in sorted_cameras if camera.get("image_url")]
    if cameras_with_image:
        preview_camera = cameras_with_image[0]
        st.markdown("**Vista previa con imagen**")
        st.table(
            [
                {
                    "id": preview_camera.get("id", ""),
                    "nombre": preview_camera.get("nombre", ""),
                    "carretera": preview_camera.get("carretera", ""),
                    "municipio": preview_camera.get("municipio", ""),
                    "image_url": preview_camera.get("image_url", ""),
                }
            ]
        )
        _display_camera_image(
            preview_camera.get("image_url", ""),
            caption=preview_camera.get("nombre", ""),
        )
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
        with st.expander(title or "Cámara"):
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
                _display_camera_image(image_url)
            else:
                st.info("No hay imagen disponible.")

            maps_url = _maps_url_from_item(camera)
            if maps_url:
                st.markdown(f"[Ver en Google Maps]({maps_url})")

            source_url = camera.get("source_url")
            if source_url:
                st.markdown(f"[Fuente original]({source_url})")


def _display_camera_image(image_url: str, caption: str | None = None) -> None:
    if not image_url:
        st.info("No hay imagen disponible.")
        return

    try:
        st.image(image_url, caption=caption, use_container_width=True)
    except Exception as exc:
        st.warning(f"No se pudo renderizar la imagen: {exc}")
    st.markdown(f"[Ver imagen original]({image_url})")


def _display_vision_result(result: dict) -> None:
    st.warning(
        "Análisis preliminar: no confirma accidentes oficialmente. "
        "Debe revisarse con fuentes operativas y criterio humano."
    )
    risk_col, label_col, confidence_col = st.columns(3)
    risk_col.metric("Riesgo", result.get("risk_level", "no disponible"))
    label_col.metric("Etiqueta", result.get("label", "no disponible"))
    confidence = result.get("confidence")
    confidence_col.metric(
        "Confianza",
        "n/d" if confidence is None else f"{float(confidence):.2f}",
    )
    reason = result.get("reason")
    if reason:
        st.write(reason)

    detections = result.get("detections") or []
    if detections:
        st.markdown("**Objetos detectados**")
        _display_detection_summary(detections)
    else:
        st.info("No se detectaron objetos relevantes en la imagen.")

    image_url = result.get("image_url")
    if image_url:
        _display_camera_image(image_url, caption=result.get("camera_name"))


def _display_detection_summary(detections: list[dict]) -> None:
    counts = Counter(
        detection.get("class_name")
        for detection in detections
        if detection.get("class_name")
    )
    vehicle_total = sum(
        counts.get(class_name, 0)
        for class_name in ("car", "truck", "bus", "motorcycle")
    )

    lines = [
        _count_label(vehicle_total, "vehiculo", "vehiculos"),
        _count_label(counts.get("car", 0), "coche", "coches"),
    ]
    for class_name, singular, plural in [
        ("truck", "camion", "camiones"),
        ("bus", "autobus", "autobuses"),
        ("motorcycle", "motocicleta", "motocicletas"),
        ("bicycle", "bicicleta", "bicicletas"),
    ]:
        count = counts.get(class_name, 0)
        if count:
            lines.append(_count_label(count, singular, plural))

    lines.append(_count_label(counts.get("person", 0), "persona", "personas"))
    st.markdown("\n".join(lines))

    if counts.get("person", 0):
        st.warning("Atención: se detectaron personas en la escena.")


def _count_label(count: int, singular: str, plural: str) -> str:
    label = singular if count == 1 else plural
    return f"- {count} {label}"


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
        st.info("Pulsa el botón para descargar incidencias reales desde Trafikoa.")

with tab_cameras:
    st.subheader("Cámaras")
    if st.button("Descargar cámaras", use_container_width=True):
        try:
            payload = get_json("/camaras")
            st.session_state["cameras"] = payload["items"]
        except requests.RequestException as exc:
            st.error(f"No se pudieron descargar las cámaras: {exc}")

    cameras = st.session_state.get("cameras", [])
    st.metric("Total", len(cameras))

    st.markdown("**Buscar cámaras procesadas**")
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
            "Límite",
            min_value=1,
            max_value=100,
            value=10,
            key="camera_search_limit",
        )
    camera_only_with_image = st.checkbox(
        "Mostrar solo cámaras con imagen",
        value=True,
        key="camera_search_only_with_image",
    )

    if "camera_search_results" not in st.session_state:
        try:
            payload = get_json(
                "/camaras/search",
                params={"only_with_image": True, "limit": 5},
            )
            st.session_state["camera_search_results"] = payload["items"]
            st.session_state["camera_search_count"] = payload["count"]
        except requests.RequestException as exc:
            st.warning(f"No se pudieron precargar cámaras con imagen: {exc}")

    if st.button("Buscar cámaras", use_container_width=True):
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
            st.session_state["camera_search_count"] = payload["count"]
            st.success(f"Cámaras encontradas: {payload['count']}")
        except requests.RequestException as exc:
            st.error(f"No se pudieron buscar cámaras: {exc}")

    camera_search_results = st.session_state.get("camera_search_results", [])
    if camera_search_results:
        st.markdown("**Resultados de búsqueda**")
        st.caption(
            f"Mostrando {len(camera_search_results)} de "
            f"{st.session_state.get('camera_search_count', len(camera_search_results))} cámaras encontradas."
        )
        _display_camera_results(camera_search_results)
    else:
        st.info("No hay resultados de cámaras procesadas para los filtros actuales.")

    if cameras:
        cameras = _sort_cameras_for_display(cameras)
        st.dataframe(cameras, use_container_width=True, hide_index=True)

        cameras_with_image = [camera for camera in cameras if camera.get("image_url")]
        if cameras_with_image:
            labels = [
                f"{camera.get('id', '')} - {camera.get('nombre', '')}"
                for camera in cameras_with_image
            ]
            selected_label = st.selectbox("Cámara con imagen", labels)
            selected_camera = cameras_with_image[labels.index(selected_label)]
            _display_camera_image(
                selected_camera.get("image_url", ""),
                caption=selected_camera.get("nombre", ""),
            )
            if st.button("Analizar imagen con visión", use_container_width=True):
                try:
                    payload = post_json(
                        "/vision/analyze-camera",
                        {"camera_id": selected_camera.get("id")},
                    )
                    st.session_state["camera_vision_result"] = payload
                except requests.RequestException as exc:
                    st.error(f"No se pudo analizar la imagen: {exc}")

            vision_result = st.session_state.get("camera_vision_result")
            if (
                vision_result
                and str(vision_result.get("camera_id") or "")
                == str(selected_camera.get("id") or "")
            ):
                st.markdown("**Análisis visual**")
                _display_vision_result(vision_result)
        else:
            st.info("No se han encontrado cámaras con image_url.")
    else:
        st.info("Pulsa el botón para descargar cámaras reales desde Trafikoa.")

with tab_congestion:
    st.subheader("Congestión")
    col_low, col_high, col_pages = st.columns(3)
    with col_low:
        umbral_bajo = st.number_input("Umbral bajo", min_value=0.0, value=50.0)
    with col_high:
        umbral_alto = st.number_input("Umbral alto", min_value=1.0, value=150.0)
    with col_pages:
        max_pages = st.number_input("Páginas flows", min_value=1, max_value=500, value=25)

    if st.button("Descargar congestión", use_container_width=True):
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
            st.error(f"No se pudo descargar la congestión: {exc}")

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
        st.info("Pulsa el botón para descargar mediciones reales de Trafikoa.")

with tab_chatbot:
    st.subheader("Chatbot")
    question = st.text_input(
        "Pregunta",
        placeholder="Ej. ¿Hay congestión en Bilbao? ¿Hay cámaras con imagen?",
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
                source_url = metadata.get("url") or metadata.get("source_url")
                if source_url:
                    st.markdown(f"[Abrir fuente original]({source_url})")
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

        known_sources = {"Ayuntamiento de Bilbao", "DEIA - Bizkaimove", "Bluesky"}
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
        st.info("Pulsa el botón para construir el corpus multifuente.")

with tab_rag:
    st.subheader("Estado RAG")
    if st.button("Actualizar índice RAG ahora", use_container_width=True):
        try:
            st.session_state["rag_status"] = post_json("/rag/refresh")
            st.success("Índice RAG actualizado.")
        except requests.RequestException as exc:
            st.error(f"No se pudo actualizar el índice RAG: {exc}")

    try:
        rag_status = st.session_state.get("rag_status") or get_json("/rag/status")
        _display_rag_status(rag_status)
    except requests.RequestException as exc:
        st.error(f"No se pudo obtener el estado RAG: {exc}")

    st.subheader("Búsqueda RAG básica")
    documents = st.text_area(
        "Documentos para indexar",
        placeholder="Un documento por línea. Ej: La A-8 presenta retenciones...",
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
            st.error(f"No se pudo ejecutar la búsqueda: {exc}")

with tab_vision:
    st.subheader("Visión por computador")
    st.warning(
        "Análisis preliminar: detecta objetos y posibles anomalías visuales, "
        "pero no confirma accidentes oficialmente."
    )

    if st.button("Cargar cámaras con imagen", use_container_width=True):
        try:
            payload = get_json(
                "/camaras/search",
                params={"only_with_image": True, "limit": 25},
            )
            st.session_state["vision_cameras"] = payload.get("items", [])
        except requests.RequestException as exc:
            st.error(f"No se pudieron cargar cámaras con imagen: {exc}")

    if "vision_cameras" not in st.session_state:
        try:
            payload = get_json(
                "/camaras/search",
                params={"only_with_image": True, "limit": 10},
            )
            st.session_state["vision_cameras"] = payload.get("items", [])
        except requests.RequestException:
            st.session_state["vision_cameras"] = []

    vision_cameras = st.session_state.get("vision_cameras", [])
    if vision_cameras:
        labels = [
            " | ".join(
                str(value)
                for value in [
                    camera.get("id"),
                    camera.get("nombre"),
                    camera.get("carretera"),
                    camera.get("municipio"),
                ]
                if value
            )
            for camera in vision_cameras
        ]
        selected_label = st.selectbox("Cámara", labels, key="vision_camera_select")
        selected_camera = vision_cameras[labels.index(selected_label)]
        _display_camera_image(
            selected_camera.get("image_url", ""),
            caption=selected_camera.get("nombre", ""),
        )

        if st.button("Analizar cámara seleccionada", use_container_width=True):
            try:
                payload = post_json(
                    "/vision/analyze-camera",
                    {"camera_id": selected_camera.get("id")},
                )
                st.session_state["vision_result"] = payload
            except requests.RequestException as exc:
                st.error(f"No se pudo analizar la cámara: {exc}")

        result = st.session_state.get("vision_result")
        if result:
            _display_vision_result(result)
    else:
        st.info("No hay cámaras con imagen cargadas para analizar.")

    st.markdown("**Analizar URL de imagen**")
    custom_image_url = st.text_input("Image URL", key="vision_custom_image_url")
    if st.button("Analizar URL", use_container_width=True):
        try:
            payload = post_json(
                "/vision/analyze-camera",
                {"image_url": custom_image_url.strip()},
            )
            st.session_state["vision_custom_result"] = payload
        except requests.RequestException as exc:
            st.error(f"No se pudo analizar la URL: {exc}")

    custom_result = st.session_state.get("vision_custom_result")
    if custom_result:
        _display_vision_result(custom_result)
