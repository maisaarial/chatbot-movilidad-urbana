from enum import Enum


class CongestionLevel(str, Enum):
    LOW = "baja"
    MEDIUM = "media"
    HIGH = "alta"


def calculate_congestion_level(
    speed_kmh: float,
    free_flow_speed_kmh: float = 80,
    incidents_count: int = 0,
) -> CongestionLevel:
    """Estimate congestion from current speed and nearby incidents."""
    if free_flow_speed_kmh <= 0:
        raise ValueError("free_flow_speed_kmh must be greater than 0")
    if speed_kmh < 0:
        raise ValueError("speed_kmh cannot be negative")
    if incidents_count < 0:
        raise ValueError("incidents_count cannot be negative")

    speed_ratio = speed_kmh / free_flow_speed_kmh

    if speed_ratio < 0.45 or incidents_count >= 3:
        return CongestionLevel.HIGH
    if speed_ratio < 0.75 or incidents_count >= 1:
        return CongestionLevel.MEDIUM
    return CongestionLevel.LOW
