import csv
from datetime import date
from html import unescape
from pathlib import Path
from typing import Any

from src.config import settings
from src.congestion import CongestionLevel, calcular_congestion
from src.trafikoa.client import TrafikoaAPIError, TrafikoaClient

SOURCE_NAMES = {
    "1": "Gobierno Pais Vasco",
    "2": "Diputacion Foral de Bizkaia",
    "3": "Diputacion Foral de Alava",
    "4": "Diputacion Foral de Gipuzkoa",
    "5": "Ayuntamiento Bilbao",
    "6": "Ayuntamiento Vitoria-Gasteiz",
    "7": "Ayuntamiento de Donostia-San Sebastian",
}

CONGESTION_COLUMNS = [
    "timestamp",
    "carretera",
    "municipio",
    "provincia",
    "valor_trafico",
    "unidad",
    "congestion",
    "fuente",
    "rag_text",
]


def get_congestion_records(
    client: TrafikoaClient | None = None,
    target_date: date | None = None,
    umbral_bajo: float | None = None,
    umbral_alto: float | None = None,
    max_pages: int | None = None,
    source_id: int | None = None,
) -> list[dict[str, Any]]:
    """Build congestion records from real Trafikoa flow measurements.

    The current first version uses totalVehicles as the traffic value. This is
    a real intensity measurement from Trafikoa flows, classified with
    configurable thresholds until a richer domain model is added.
    """
    client = client or TrafikoaClient.from_env()
    target_date = target_date or date.today()
    umbral_bajo = umbral_bajo if umbral_bajo is not None else settings.congestion_low_threshold
    umbral_alto = umbral_alto if umbral_alto is not None else settings.congestion_high_threshold
    max_pages = max_pages if max_pages is not None else settings.trafikoa_congestion_max_flow_pages
    source_id = source_id if source_id is not None else settings.trafikoa_congestion_source_id

    flow_endpoint = _build_flow_endpoint(target_date, source_id)
    flow_payloads = client.get_paginated(flow_endpoint, max_pages=max_pages)
    meters_endpoint = f"{settings.trafikoa_meters_path.rstrip('/')}/bySource/{source_id}"
    try:
        meter_payloads = client.get_paginated(meters_endpoint)
    except TrafikoaAPIError:
        # Flow measurements are still real even if Trafikoa cannot provide
        # meter metadata for this source at this moment.
        meter_payloads = []
    meters_by_id = _meters_by_id(meter_payloads)

    raw_payload = {
        "flows_endpoint": client.build_url(flow_endpoint),
        "meters_endpoint": client.build_url(meters_endpoint),
        "date": target_date.isoformat(),
        "source_id": source_id,
        "max_pages": max_pages,
        "thresholds": {
            "umbral_bajo": umbral_bajo,
            "umbral_alto": umbral_alto,
            "unidad": "vehiculos/intervalo",
        },
        "flow_pages": flow_payloads,
        "meter_pages": meter_payloads,
    }
    client.save_json(raw_payload, "congestion_raw.json")

    flows = []
    for payload in flow_payloads:
        flows.extend(_normalise_flow_items(payload))

    records = [
        _flow_to_congestion_record(
            flow=flow,
            meter=meters_by_id.get(_clean_text(flow.get("meterId")), {}),
            umbral_bajo=umbral_bajo,
            umbral_alto=umbral_alto,
        )
        for flow in flows
    ]
    records = [record for record in records if record is not None]
    _save_csv(records, settings.processed_data_dir / "congestion.csv", CONGESTION_COLUMNS)
    return records


def congestion_records_to_rag_documents(records: list[dict[str, Any]]) -> list[str]:
    return [record["rag_text"] for record in records if record.get("rag_text")]


def _build_flow_endpoint(target_date: date, source_id: int | None) -> str:
    endpoint = settings.trafikoa_flows_path.format(
        year=target_date.year,
        month=target_date.month,
        day=target_date.day,
    )
    if source_id is None:
        return endpoint
    return f"{endpoint.rstrip('/')}/bySource/{source_id}"


def _normalise_flow_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        value = payload.get("flows")
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _meters_by_id(payloads: list[Any]) -> dict[str, dict[str, Any]]:
    meters = {}
    for payload in payloads:
        for feature in _normalise_meter_items(payload):
            properties = feature.get("properties", {})
            meter_id = _clean_text(properties.get("meterId"))
            if meter_id:
                meters[meter_id] = properties
    return meters


def _normalise_meter_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        value = payload.get("features")
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _flow_to_congestion_record(
    flow: dict[str, Any],
    meter: dict[str, Any],
    umbral_bajo: float,
    umbral_alto: float,
) -> dict[str, Any] | None:
    value = _to_float(flow.get("totalVehicles"))
    if value is None:
        value = _to_float(flow.get("occupancy"))
        unit = "ocupacion"
    else:
        unit = "vehiculos/intervalo"

    if value is None:
        level = _level_from_service(flow.get("levelOfService"))
        if level is None:
            return None
        value = _to_float(flow.get("levelOfService")) or 0.0
        unit = "nivel_servicio"
    else:
        level = calcular_congestion(value, umbral_bajo, umbral_alto)

    source_id = _clean_text(flow.get("sourceId") or meter.get("sourceId"))
    road = _first_text(
        meter,
        "road",
        "description",
        "system",
        "etd",
    )
    if not road:
        meter_code = _clean_text(meter.get("meterCode"))
        meter_id = _clean_text(flow.get("meterId"))
        road = f"medidor:{meter_code or meter_id}"
    timestamp = _build_timestamp(flow.get("meterDate"), flow.get("timeRank"))

    record = {
        "timestamp": timestamp,
        "carretera": road,
        "municipio": _clean_text(meter.get("municipality")),
        "provincia": _clean_text(meter.get("province")),
        "valor_trafico": value,
        "unidad": unit,
        "congestion": level.value,
        "fuente": SOURCE_NAMES.get(source_id, source_id),
    }
    record["rag_text"] = _to_rag_text(record)
    return record


def _level_from_service(value: Any) -> CongestionLevel | None:
    raw_value = _clean_text(value).lower()
    if not raw_value:
        return None
    if raw_value in {"1", "verde", "green"}:
        return CongestionLevel.LOW
    if raw_value in {"2", "amarillo", "yellow"}:
        return CongestionLevel.MEDIUM
    if raw_value in {"3", "rojo", "red"}:
        return CongestionLevel.HIGH
    return None


def _build_timestamp(meter_date: Any, time_rank: Any) -> str:
    date_part = _clean_text(meter_date)
    time_part = _clean_text(time_rank).split(" - ")[0]
    if not date_part:
        return time_part
    if not time_part:
        return date_part
    return f"{date_part}T{time_part}"


def _to_rag_text(record: dict[str, Any]) -> str:
    location = ", ".join(
        value
        for value in [
            record.get("carretera"),
            record.get("municipio"),
            record.get("provincia"),
        ]
        if value
    )
    return (
        f"Congestion {record['congestion']} en {location}. "
        f"Valor de trafico: {record['valor_trafico']} {record['unidad']}. "
        f"Fecha: {record['timestamp']}. Fuente: {record['fuente']}."
    )


def _save_csv(rows: list[dict[str, Any]], path: Path, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _first_text(values: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = _clean_text(values.get(key))
        if value:
            return value
    return ""


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return unescape(str(value)).strip()


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
