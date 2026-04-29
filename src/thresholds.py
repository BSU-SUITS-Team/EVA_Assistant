"""
Telemetry thresholds and units imported from docs/*.md

Provide a central place to keep numeric alert thresholds and expected units
for telemetry fields. Values are conservative suggestions derived from
docs/eva-telemetry-ranges.md and docs/rover-telemetry-ranges.md.
"""
from typing import Dict, Optional, Tuple

# Per-field numeric thresholds. Use (min, max) where applicable. None means
# not specified in source material.
THRESHOLDS: Dict[str, Tuple[Optional[float], Optional[float]]] = {
    # EVA fields
    "primary_battery_level": (20.0, 100.0),
    "secondary_battery_level": (20.0, 100.0),
    "oxy_pri_storage": (20.0, 100.0),
    "oxy_sec_storage": (20.0, 100.0),
    "oxy_pri_pressure": (600.0, None),
    "oxy_sec_pressure": (600.0, None),
    "coolant_storage": (80.0, None),
    "heart_rate": (50.0, None),
    "oxy_consumption": (0.05, None),
    "co2_production": (0.05, None),
    "suit_pressure_total": (3.5, None),
    "helmet_pressure_co2": (0.0, None),
    "fan_pri_rpm": (0.0, None),
    "fan_sec_rpm": (0.0, None),

    # Rover fields
    "pitch": (-50.0, 50.0),
    "roll": (0.0, 50.0),
    "speed": (0.0, 18.0),
    "throttle": (0.0, 100.0),
    "steering": (None, None),
    "distance_traveled": (0.0, None),
    "surface_incline": (-50.0, 50.0),
    "distance_from_base": (0.0, 2500.0),
    "oxygen_tank": (25.0, 100.0),
    "oxygen_pressure": (2997.0, 3000.0),
    "fan_pri_rpm_rover": (29999.0, 30005.0),
}

# Units mapping for known fields. Use plain strings like '%', 'psi', 'm', 'rpm'.
UNITS: Dict[str, str] = {
    # EVA
    "primary_battery_level": "%",
    "secondary_battery_level": "%",
    "oxy_pri_storage": "%",
    "oxy_sec_storage": "%",
    "oxy_pri_pressure": "psi",
    "oxy_sec_pressure": "psi",
    "coolant_storage": "%",
    "heart_rate": "bpm",
    "oxy_consumption": "psi/min",
    "co2_production": "psi/min",
    "suit_pressure_total": "psi",
    "helmet_pressure_co2": "psi",
    "fan_pri_rpm": "rpm",
    "fan_sec_rpm": "rpm",

    # Rover
    "pitch": "deg",
    "roll": "deg",
    "speed": "m/s",
    "throttle": "%",
    "steering": "unitless",
    "distance_traveled": "m",
    "surface_incline": "deg",
    "distance_from_base": "m",
    "oxygen_tank": "%",
    "oxygen_pressure": "psi",
    "fan_pri_rpm_rover": "rpm",
}


def get_threshold(field: str):
    """Return (min, max) tuple for a field, or (None, None) if unknown."""
    return THRESHOLDS.get(field, (None, None))


def get_unit(field: str) -> Optional[str]:
    """Return unit string for a field, or None if unknown."""
    return UNITS.get(field)
