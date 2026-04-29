"""
Field routing and question matching into telemetry field candidates.
Handles field metadata, aliases, direct routing, and question tokenization.
"""

import re
from typing import Any, Dict, List, Optional


FIELD_METADATA = {
    # Battery fields
    "battery": {"unit": "%", "label": "Battery"},
    "battery_level": {"unit": "%", "label": "Battery level"},
    "primary_battery_level": {"unit": "%", "label": "Primary battery level"},
    "secondary_battery_level": {"unit": "%", "label": "Secondary battery level"},
    
    # Oxygen storage
    "oxy_pri_storage": {"unit": "%", "label": "Primary O2 storage"},
    "oxy_sec_storage": {"unit": "%", "label": "Secondary O2 storage"},
    
    # Oxygen pressure
    "oxy_pri_pressure": {"unit": "psi", "label": "Primary O2 pressure"},
    "oxy_sec_pressure": {"unit": "psi", "label": "Secondary O2 pressure"},
    
    # Oxygen consumption
    "oxy_consumption": {"unit": "psi/min", "label": "O2 consumption"},
    "oxy_pri_consumption": {"unit": "psi/min", "label": "Primary O2 consumption"},
    
    # CO2
    "co2_production": {"unit": "psi/min", "label": "CO2 production"},
    "co2_pressure": {"unit": "psi", "label": "CO2 pressure"},
    "suit_pressure_co2": {"unit": "psi", "label": "Suit CO2 pressure"},
    "helmet_pressure_co2": {"unit": "psi", "label": "Helmet CO2 pressure"},
    "suit_pressure_other": {"unit": "psi", "label": "Suit pressure other"},
    
    # Suit pressure
    "suit_pressure": {"unit": "psi", "label": "Suit pressure"},
    "suit_pressure_oxy": {"unit": "psi", "label": "Suit O2 pressure"},
    "suit_pressure_co2": {"unit": "psi", "label": "Suit CO2 pressure"},
    "suit_pressure_total": {"unit": "psi", "label": "Suit total pressure"},
    
    # Fans
    "primary_fan": {"unit": "rpm", "label": "Primary fan"},
    "secondary_fan": {"unit": "rpm", "label": "Secondary fan"},
    "fan_pri_rpm": {"unit": "rpm", "label": "Primary fan"},
    "fan_sec_rpm": {"unit": "rpm", "label": "Secondary fan"},
    
    # Scrubbers
    "scrubber_primary": {"unit": "%", "label": "Scrubber primary"},
    "scrubber_secondary": {"unit": "%", "label": "Scrubber secondary"},
    "scrubber_a_co2_storage": {"unit": "%", "label": "Scrubber A CO2 storage"},
    "scrubber_b_co2_storage": {"unit": "%", "label": "Scrubber B CO2 storage"},
    
    # Temperature
    "temperature": {"unit": "°C", "label": "Temperature"},
    "external_temp": {"unit": "°C", "label": "External temperature"},
    
    # Coolant
    "coolant_storage": {"unit": "%", "label": "Coolant storage"},
    "coolant_liquid_pressure": {"unit": "psi", "label": "Coolant liquid pressure"},
    "coolant_gas_pressure": {"unit": "psi", "label": "Coolant gas pressure"},
    
    # Biometrics
    "heart_rate": {"unit": "bpm", "label": "Heart rate"},
    
    # Location
    "posx": {"unit": "m", "label": "X coordinate"},
    "posy": {"unit": "m", "label": "Y coordinate"},
    "heading": {"unit": "°", "label": "Heading"},
    "rover_pos_x": {"unit": "m", "label": "Rover X coordinate"},
    "rover_pos_y": {"unit": "m", "label": "Rover Y coordinate"},
    "last_known_x": {"unit": "m", "label": "Last known X"},
    "last_known_y": {"unit": "m", "label": "Last known Y"},
    
    # Rover telemetry
    "oxygen_storage": {"unit": "%", "label": "Oxygen storage"},
    "oxygen_pressure": {"unit": "psi", "label": "Oxygen pressure"},
    "oxygen_tank": {"unit": "%", "label": "Oxygen tank"},
}


def _tokenize(text: str) -> List[str]:
    return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 1]


def _normalize_question(question: str) -> str:
    return question.lower().replace("02", "o2")


def _humanize_field_key(field_key: str) -> str:
    text = field_key.replace("_", " ").strip()
    return text if text else "value"


def _clean_label(label: str, field_key: str) -> str:
    cleaned = (label or "").strip()
    if cleaned and cleaned.lower() != "unknown":
        return cleaned
    return _humanize_field_key(field_key)


def _field_aliases() -> Dict[str, List[str]]:
    return {
        # Battery fields
        "battery": ["battery", "battery level", "battery charge", "battery percentage"],
        "battery_level": ["battery level", "battery charge", "battery percentage"],
        "primary_battery_level": ["primary battery level", "primary battery", "battery level", "battery percentage"],
        "secondary_battery_level": ["secondary battery level", "secondary battery"],
        
        # Oxygen storage
        "oxy_pri_storage": ["primary o2 storage", "primary oxygen storage", "pri o2 storage", "o2 storage"],
        "oxy_sec_storage": ["secondary o2 storage", "secondary oxygen storage", "sec o2 storage"],
        
        # Oxygen pressure
        "oxy_pri_pressure": ["primary o2 pressure", "primary oxygen pressure", "pri o2 pressure", "o2 pressure", "primary pressure"],
        "oxy_sec_pressure": ["secondary o2 pressure", "secondary oxygen pressure", "sec o2 pressure", "secondary pressure"],
        
        # Oxygen consumption
        "oxy_pri_consumption": ["primary o2 consumption", "primary oxygen consumption", "o2 consumption", "consumption"],
        "oxy_consumption": ["o2 consumption", "oxygen consumption", "consumption rate", "consumption"],
        
        # CO2
        "co2_production": ["co2 production", "carbon dioxide production"],
        "co2_pressure": ["co2 pressure", "co2 partial pressure", "carbon dioxide pressure"],
        "suit_pressure_co2": ["suit co2 pressure", "co2 pressure", "co2 partial pressure"],
        "helmet_pressure_co2": ["helmet co2 pressure", "co2 pressure"],
        
        # Suit pressure
        "suit_pressure": ["suit pressure", "pressure"],
        "suit_pressure_oxy": ["suit o2 pressure", "suit oxygen pressure", "suit oxy pressure"],
        "suit_pressure_co2": ["suit co2 pressure"],
        "suit_pressure_total": ["suit total pressure", "total pressure"],
        "suit_pressure_other": ["suit other pressure", "suit unknown pressure"],
        
        # Fans
        "primary_fan": ["primary fan", "fan speed", "primary fan speed"],
        "secondary_fan": ["secondary fan", "secondary fan speed"],
        "fan_pri_rpm": ["primary fan", "fan speed", "primary fan speed", "fan rpm"],
        "fan_sec_rpm": ["secondary fan", "secondary fan speed", "fan rpm"],
        
        # Scrubbers
        "scrubber_primary": ["scrubber primary", "primary scrubber", "scrubber", "primary scrubber efficiency"],
        "scrubber_secondary": ["scrubber secondary", "secondary scrubber"],
        "scrubber_a_co2_storage": ["scrubber a", "scrubber primary", "scrubber co2"],
        "scrubber_b_co2_storage": ["scrubber b", "scrubber secondary", "scrubber co2"],
        
        # Temperature
        "temperature": ["temperature", "temp", "suit temperature"],
        "external_temp": ["external temperature", "external temp"],
        
        # Coolant
        "coolant_storage": ["coolant storage", "coolant reserve", "coolant tank"],
        "coolant_liquid_pressure": ["coolant liquid pressure", "coolant pressure"],
        "coolant_gas_pressure": ["coolant gas pressure"],
        
        # Biometrics
        "heart_rate": ["heart rate", "pulse", "heart beat"],
        
        # Location
        "posx": ["x coordinate", "x position", "x location", "position x", "eva x"],
        "posy": ["y coordinate", "y position", "y location", "position y", "eva y"],
        "heading": ["heading", "direction", "bearing"],
        "rover_pos_x": ["rover x", "rover x coordinate", "rover position x"],
        "rover_pos_y": ["rover y", "rover y coordinate", "rover position y"],
        "last_known_x": ["last known x", "last x", "ltv x"],
        "last_known_y": ["last known y", "last y", "ltv y"],
        "oxygen_storage": ["rover oxygen storage", "oxygen storage", "o2 storage"],
        "oxygen_pressure": ["rover oxygen pressure", "oxygen pressure", "o2 pressure"],
        "oxygen_tank": ["oxygen tank"],
    }


def _direct_field_candidates(question: str) -> List[str]:
    normalized_question = _normalize_question(question)

    if "battery" in normalized_question:
        return ["battery", "battery_level", "primary_battery_level", "secondary_battery_level"]

    if "fan" in normalized_question:
        if "secondary" in normalized_question or "sec" in normalized_question:
            return ["secondary_fan", "fan_sec_rpm"]
        if "primary" in normalized_question or "pri" in normalized_question:
            return ["primary_fan", "fan_pri_rpm"]
        return ["primary_fan", "fan_pri_rpm", "secondary_fan", "fan_sec_rpm"]

    if "scrubber" in normalized_question:
        if "secondary" in normalized_question or "sec" in normalized_question or " b" in normalized_question or "b " in normalized_question or normalized_question.endswith("b"):
            return ["scrubber_secondary", "scrubber_b_co2_storage"]
        if "primary" in normalized_question or "pri" in normalized_question or " a" in normalized_question or "a " in normalized_question or normalized_question.endswith("a"):
            return ["scrubber_primary", "scrubber_a_co2_storage"]
        return ["scrubber_primary", "scrubber_a_co2_storage", "scrubber_secondary", "scrubber_b_co2_storage"]

    if "coolant" in normalized_question:
        if "liquid" in normalized_question or "pressure" in normalized_question:
            return ["coolant_liquid_pressure", "coolant_gas_pressure"]
        if "storage" in normalized_question:
            return ["coolant_storage"]
        return ["coolant_storage", "coolant_liquid_pressure", "coolant_gas_pressure"]

    if "temperature" in normalized_question or "temp" in normalized_question:
        return ["temperature"]

    if "heading" in normalized_question or "direction" in normalized_question:
        return ["heading"]

    if "coordinate" in normalized_question or "location" in normalized_question or "position" in normalized_question:
        # For "coordinates" plural, return both x and y
        if "coordinates" in normalized_question or ("coordinate" in normalized_question and "x" not in normalized_question and "y" not in normalized_question):
            return ["posx", "posy"]
        if "x" in normalized_question:
            return ["posx", "rover_pos_x", "last_known_x"]
        if "y" in normalized_question:
            return ["posy", "rover_pos_y", "last_known_y"]
        return ["posx", "posy", "rover_pos_x", "rover_pos_y", "heading"]

    if "co2" in normalized_question and "pressure" in normalized_question:
        return ["suit_pressure_co2", "helmet_pressure_co2", "co2_pressure"]

    if "co2" in normalized_question and "production" in normalized_question:
        return ["co2_production"]

    if "pressure" in normalized_question:
        if "secondary" in normalized_question or "sec" in normalized_question:
            return ["oxy_sec_pressure"]
        if "primary" in normalized_question or "pri" in normalized_question or "o2" in normalized_question or "oxygen" in normalized_question:
            return ["oxy_pri_pressure"]
        if "suit" in normalized_question or "total" in normalized_question:
            return ["suit_pressure_total", "suit_pressure", "suit_pressure_oxy", "suit_pressure_co2"]
        if "helmet" in normalized_question:
            return ["helmet_pressure_co2"]
        return ["oxy_pri_pressure", "oxy_sec_pressure"]

    if "storage" in normalized_question:
        if "secondary" in normalized_question or "sec" in normalized_question:
            return ["oxy_sec_storage"]
        if "primary" in normalized_question or "pri" in normalized_question or "o2" in normalized_question or "oxygen" in normalized_question:
            return ["oxy_pri_storage"]
        if "coolant" in normalized_question:
            return ["coolant_storage"]
        return ["oxy_pri_storage", "oxy_sec_storage"]

    if any(token in normalized_question for token in ["consumption", "consume", "consumed", "usage", "draw"]):
        return ["oxy_consumption", "oxy_pri_consumption"]

    if "heart rate" in normalized_question or "pulse" in normalized_question:
        return ["heart_rate"]

    return []


def _extract_entity_label(field_path: str) -> str:
    parts = field_path.split(".")
    if "telemetry" in parts:
        telemetry_index = parts.index("telemetry")
        if telemetry_index + 1 < len(parts):
            entity = parts[telemetry_index + 1]
            if entity.lower().startswith("eva"):
                return entity.upper()
            return entity.upper()
    if len(parts) >= 2:
        candidate = parts[-2]
        if candidate.lower().startswith("eva"):
            return candidate.upper()
        return candidate.upper()
    return "UNKNOWN"


def _extract_requested_entity(question: str) -> Optional[str]:
    """Extract EVA1 or EVA2 from question if specified."""
    normalized = question.lower()
    if "eva1" in normalized or "eva 1" in normalized:
        return "eva1"
    if "eva2" in normalized or "eva 2" in normalized:
        return "eva2"
    return None


def _filter_rows_by_entity(rows: List[Dict[str, Any]], entity: Optional[str]) -> List[Dict[str, Any]]:
    """Filter rows to match the specified entity (eva1 or eva2)."""
    if not entity:
        return rows
    
    entity_lower = entity.lower()
    filtered = [row for row in rows if entity_lower in str(row.get("field_path", "")).lower()]
    return filtered if filtered else rows  # Return all if none match


def _score_row(question_tokens: List[str], row: Dict[str, Any]) -> int:
    haystack = " ".join(
        [
            row.get("field_path", ""),
            row.get("label", ""),
            row.get("unit", ""),
        ]
    ).lower()
    score = 0
    for token in question_tokens:
        if token in haystack:
            score += 1
    return score


def _row_tokens(row: Dict[str, Any]) -> List[str]:
    return _tokenize(" ".join([row.get("field_path", ""), row.get("label", ""), row.get("unit", "")]))


def _question_matches_field(question: str, row: Dict[str, Any]) -> bool:
    normalized_question = _normalize_question(question)
    question_tokens = set(_tokenize(normalized_question))
    aliases = _field_aliases()

    field_path = str(row.get("field_path", "")).lower()
    field_key = str(row.get("field_key", "")).lower()
    label = str(row.get("label", "")).lower()
    haystack = " ".join([field_path, field_key, label]).lower()

    # Explicit key routing for common oxygen pressure/storage questions.
    if {"primary", "o2", "pressure"} <= question_tokens or {"primary", "oxygen", "pressure"} <= question_tokens:
        return field_key == "oxy_pri_pressure" or "oxy_pri_pressure" in field_path
    if {"secondary", "o2", "pressure"} <= question_tokens or {"secondary", "oxygen", "pressure"} <= question_tokens:
        return field_key == "oxy_sec_pressure" or "oxy_sec_pressure" in field_path

    # Strong exact matches first.
    for alias_list in aliases.values():
        for alias in alias_list:
            if alias in normalized_question and alias in haystack:
                return True

    # Then token overlap, but require the core topic token to be present.
    core_tokens = {
        "battery", "pressure", "storage", "heart", "co2", "oxygen", "o2", "production",
        "fan", "scrubber", "coolant", "temperature", "temp", "coordinate", "location",
        "heading", "direction", "bearing", "consumption", "consume"
    }
    if not (question_tokens & core_tokens):
        return False

    has_pressure_intent = "pressure" in question_tokens or "pressures" in question_tokens
    has_storage_intent = "storage" in question_tokens or "stored" in question_tokens
    has_consumption_intent = "consumption" in question_tokens or "consume" in question_tokens or "consumed" in question_tokens

    # Keep storage and pressure separate unless the question explicitly asks for both.
    if has_pressure_intent and not has_storage_intent:
        if "pressure" not in haystack and "co2" not in haystack:
            return False
        if "storage" in haystack:
            return False

    if has_pressure_intent and has_storage_intent:
        # A query asking for pressure of a storage system should prefer actual pressure fields.
        if "pressure" not in haystack:
            return False
        if "storage" in haystack and "pressure" not in field_key:
            return False

    if has_storage_intent and not has_pressure_intent:
        if "storage" not in haystack:
            return False
        if "pressure" in haystack and "storage" not in haystack:
            return False

    if has_consumption_intent:
        if "consumption" not in haystack and "consume" not in haystack and "usage" not in haystack:
            return False

    # Require both CO2 and pressure for CO2-pressure questions so production values do not match.
    if "co2" in question_tokens and "pressure" in question_tokens:
        if "pressure" not in haystack or "co2" not in haystack:
            return False

    token_score = sum(1 for token in question_tokens if token in haystack)
    return token_score >= 2


def _find_direct_matches(question: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    candidates = _direct_field_candidates(question)
    if not candidates:
        return []

    matched: List[Dict[str, Any]] = []
    
    # For coordinates, we want to collect ALL candidate matches (both x and y)
    is_coordinates_query = ("coordinate" in question.lower() or "position" in question.lower()) and "x" not in question.lower() and "y" not in question.lower()
    
    for candidate in candidates:
        for row in rows:
            field_key = str(row.get("field_key", "")).lower()
            field_path = str(row.get("field_path", "")).lower()
            label = str(row.get("label", "")).lower()

            if candidate in field_key or candidate in field_path:
                matched.append(row)
            elif candidate.replace("_", " ") in label:
                matched.append(row)

        # For non-coordinate queries, return after first candidate match
        if matched and not is_coordinates_query:
            # Filter by requested entity if specified
            requested_entity = _extract_requested_entity(question)
            filtered = _filter_rows_by_entity(matched, requested_entity)
            return filtered

    # For coordinate queries, filter by entity
    if matched:
        requested_entity = _extract_requested_entity(question)
        return _filter_rows_by_entity(matched, requested_entity)
    
    return matched
