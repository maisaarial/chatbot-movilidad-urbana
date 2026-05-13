from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import requests


TARGET_CLASSES = {"car", "truck", "bus", "motorcycle", "person", "bicycle"}
MODEL_NAME = "yolov8n.pt"
DOWNLOAD_TIMEOUT_SECONDS = 20
MIN_DETECTION_CONFIDENCE = 0.25

_MODEL_CACHE: Any | None = None
_MODEL_ERROR: str | None = None


class VisionModelUnavailableError(RuntimeError):
    pass


def download_camera_image(image_url: str) -> bytes:
    if not image_url or not str(image_url).strip():
        raise ValueError("Debes proporcionar una URL de imagen.")

    response = requests.get(str(image_url), timeout=DOWNLOAD_TIMEOUT_SECONDS)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    if content_type and "image" not in content_type.lower():
        raise ValueError(f"La URL no devolvio una imagen: {content_type}")
    return response.content


def detect_objects(image_path_or_bytes: str | Path | bytes) -> list[dict[str, Any]]:
    model = _load_model()
    image = _load_image(image_path_or_bytes)
    width, height = image.size

    results = model.predict(
        source=image,
        conf=MIN_DETECTION_CONFIDENCE,
        verbose=False,
    )
    detections = []
    names = getattr(model, "names", {}) or {}
    for result in results:
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            continue
        for box in boxes:
            class_id = int(box.cls[0].item())
            class_name = str(names.get(class_id, class_id))
            if class_name not in TARGET_CLASSES:
                continue
            confidence = float(box.conf[0].item())
            x1, y1, x2, y2 = [float(value) for value in box.xyxy[0].tolist()]
            detections.append(
                {
                    "class_name": class_name,
                    "confidence": round(confidence, 4),
                    "bbox": {
                        "x1": round(x1, 2),
                        "y1": round(y1, 2),
                        "x2": round(x2, 2),
                        "y2": round(y2, 2),
                    },
                    "bbox_normalized": {
                        "x1": round(x1 / width, 4) if width else 0,
                        "y1": round(y1 / height, 4) if height else 0,
                        "x2": round(x2 / width, 4) if width else 0,
                        "y2": round(y2 / height, 4) if height else 0,
                    },
                }
            )
    return detections


def analyze_camera_image(
    image_url: str,
    camera_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = camera_metadata or {}
    base_result = {
        "camera_id": _clean(metadata.get("id")),
        "camera_name": _clean(metadata.get("nombre") or metadata.get("camera_name")),
        "image_url": image_url,
        "risk_level": "bajo",
        "label": "sin_indicios",
        "confidence": 0.0,
        "detections": [],
        "reason": "",
        "timestamp": _now_iso(),
    }

    try:
        _load_model()
        image_bytes = download_camera_image(image_url)
        detections = detect_objects(image_bytes)
    except VisionModelUnavailableError as exc:
        base_result.update(
            {
                "reason": (
                    "Analisis visual no disponible: falta el modelo de vision o "
                    f"sus dependencias ({exc})."
                ),
                "model_status": "unavailable",
            }
        )
        return base_result
    except Exception as exc:
        base_result.update(
            {
                "reason": f"No se pudo analizar la imagen de la camara: {exc}",
                "model_status": "error",
            }
        )
        return base_result

    risk = classify_visual_risk(detections)
    base_result.update(risk)
    base_result["detections"] = detections
    base_result["model_status"] = "ok"
    return base_result


def classify_visual_risk(detections: list[dict[str, Any]]) -> dict[str, Any]:
    vehicles = [
        detection
        for detection in detections
        if detection.get("class_name") in {"car", "truck", "bus", "motorcycle"}
    ]
    people = [
        detection for detection in detections if detection.get("class_name") == "person"
    ]
    bicycles = [
        detection for detection in detections if detection.get("class_name") == "bicycle"
    ]

    close_pairs = _count_close_pairs(vehicles)
    people_near_vehicles = _count_people_near_vehicles(people, vehicles)
    large_vehicle_count = sum(
        1 for detection in vehicles if _bbox_area(detection) >= 0.18
    )

    reasons = []
    score = 0.0
    if people_near_vehicles:
        score += min(0.45, 0.25 + 0.1 * people_near_vehicles)
        reasons.append("personas detectadas cerca de vehiculos en la imagen")
    if len(vehicles) >= 8:
        score += 0.35
        reasons.append("acumulacion alta de vehiculos")
    elif len(vehicles) >= 5:
        score += 0.2
        reasons.append("acumulacion moderada de vehiculos")
    if close_pairs >= 5:
        score += 0.25
        reasons.append("varias detecciones de vehiculos muy juntas")
    elif close_pairs >= 2:
        score += 0.12
        reasons.append("algunas detecciones de vehiculos muy juntas")
    if large_vehicle_count >= 2:
        score += 0.2
        reasons.append("vehiculos grandes o cercanos que podrian bloquear parte del carril")
    if bicycles and vehicles:
        score += 0.08
        reasons.append("bicicletas detectadas junto a vehiculos")

    confidence = min(round(score, 3), 0.95)
    if confidence >= 0.72 and people_near_vehicles:
        return {
            "risk_level": "alto",
            "label": "posible_accidente",
            "confidence": confidence,
            "reason": (
                "Posible accidente o incidente visual: "
                + "; ".join(reasons)
                + ". Es una alerta preliminar, no una confirmacion oficial."
            ),
        }
    if confidence >= 0.35:
        return {
            "risk_level": "medio",
            "label": "posible_anomalia",
            "confidence": confidence,
            "reason": (
                "Posible anomalia visual: "
                + "; ".join(reasons)
                + ". Una sola imagen no permite confirmar un accidente."
            ),
        }
    return {
        "risk_level": "bajo",
        "label": "sin_indicios",
        "confidence": confidence,
        "reason": "Sin indicios visuales claros de accidente o anomalia en esta imagen.",
    }


def _load_model() -> Any:
    global _MODEL_CACHE, _MODEL_ERROR
    if _MODEL_CACHE is not None:
        return _MODEL_CACHE
    if _MODEL_ERROR:
        raise VisionModelUnavailableError(_MODEL_ERROR)

    try:
        from ultralytics import YOLO

        _MODEL_CACHE = YOLO(MODEL_NAME)
    except Exception as exc:
        _MODEL_ERROR = str(exc)
        raise VisionModelUnavailableError(_MODEL_ERROR) from exc
    return _MODEL_CACHE


def _load_image(image_path_or_bytes: str | Path | bytes) -> Image.Image:
    from PIL import Image

    if isinstance(image_path_or_bytes, bytes):
        image = Image.open(BytesIO(image_path_or_bytes))
    else:
        image = Image.open(image_path_or_bytes)
    return image.convert("RGB")


def _count_close_pairs(detections: list[dict[str, Any]]) -> int:
    count = 0
    for first_index, first in enumerate(detections):
        for second in detections[first_index + 1 :]:
            if _center_distance(first, second) < 0.14:
                count += 1
    return count


def _count_people_near_vehicles(
    people: list[dict[str, Any]],
    vehicles: list[dict[str, Any]],
) -> int:
    count = 0
    for person in people:
        if any(_center_distance(person, vehicle) < 0.18 for vehicle in vehicles):
            count += 1
    return count


def _center_distance(first: dict[str, Any], second: dict[str, Any]) -> float:
    first_center = _bbox_center(first)
    second_center = _bbox_center(second)
    return (
        (first_center[0] - second_center[0]) ** 2
        + (first_center[1] - second_center[1]) ** 2
    ) ** 0.5


def _bbox_center(detection: dict[str, Any]) -> tuple[float, float]:
    bbox = detection.get("bbox_normalized") or {}
    return (
        (float(bbox.get("x1", 0)) + float(bbox.get("x2", 0))) / 2,
        (float(bbox.get("y1", 0)) + float(bbox.get("y2", 0))) / 2,
    )


def _bbox_area(detection: dict[str, Any]) -> float:
    bbox = detection.get("bbox_normalized") or {}
    width = max(float(bbox.get("x2", 0)) - float(bbox.get("x1", 0)), 0)
    height = max(float(bbox.get("y2", 0)) - float(bbox.get("y1", 0)), 0)
    return width * height


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
