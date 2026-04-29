"""
EVA Assistant - Simplified version
Direct telemetry fetch + LLM arithmetic (no vector database)
Fetches telemetry every second in background
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from telemetry import get_current_telemetry, start_polling

# Optional LLM imports for natural language formatting
try:
    from langchain.llms import Ollama
    from langchain.callbacks.manager import CallbackManager
    from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_HISTORY_TURNS = 6

# Field-level metadata used to attach explicit units/labels.
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


def _is_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool))


@dataclass(frozen=True)
class TelemetryAnswer:
    value: Any
    unit: str
    label: str
    entity: str
    field_path: str
    kind: str


def _tokenize(text: str) -> List[str]:
    return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 1]


def _normalize_question(question: str) -> str:
    return question.lower().replace("02", "o2")


def _flatten_telemetry(data: Dict[str, Any], prefix: str = "") -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    for key in sorted(data.keys()):
        value = data[key]
        field_path = f"{prefix}.{key}" if prefix else key

        if isinstance(value, dict):
            rows.extend(_flatten_telemetry(value, field_path))
            continue

        if not _is_scalar(value):
            continue

        metadata = FIELD_METADATA.get(key, {})
        rows.append(
            {
                "field_path": field_path,
                "field_key": key,
                "value": value,
                "unit": metadata.get("unit", "unknown"),
                "label": metadata.get("label", key),
                "source": "telemetry_server",
            }
        )

    return rows


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


def _humanize_field_key(field_key: str) -> str:
    text = field_key.replace("_", " ").strip()
    return text if text else "value"


def _clean_label(label: str, field_key: str) -> str:
    cleaned = (label or "").strip()
    if cleaned and cleaned.lower() != "unknown":
        return cleaned
    return _humanize_field_key(field_key)


def _row_tokens(row: Dict[str, Any]) -> List[str]:
    return _tokenize(" ".join([row.get("field_path", ""), row.get("label", ""), row.get("unit", "")]))


def select_relevant_rows(question: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    question_tokens = _tokenize(question)
    if not question_tokens:
        return []

    scored_rows = [(_score_row(question_tokens, row), row) for row in rows]

    max_score = max((score for score, _ in scored_rows), default=0)
    if max_score <= 0:
        return []

    return [row for score, row in scored_rows if score == max_score or score >= max_score - 1]


def _extract_numeric_value(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace("%", "")
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


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


def _is_time_to_threshold_question(question: str) -> bool:
    normalized_question = _normalize_question(question)
    return any(
        phrase in normalized_question
        for phrase in [
            "how long until",
            "time until",
            "when will",
            "how soon until",
            "how many minutes until",
            "how many seconds until",
        ]
    )


def _is_depletion_question(question: str) -> bool:
    normalized_question = _normalize_question(question)
    return any(
        phrase in normalized_question
        for phrase in [
            "run out",
            "runs out",
            "empty",
            "deplete",
            "depleted",
            "hits zero",
            "until zero",
            "out of",
        ]
    )


def _find_rate_row(rows: List[Dict[str, Any]], current_row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    current_field_path = str(current_row.get("field_path", "")).lower()
    current_label = str(current_row.get("label", "")).lower()
    current_key = str(current_row.get("field_key", "")).lower()
    base_tokens = set(_tokenize(" ".join([current_field_path, current_label, current_key])))

    rate_keywords = {"rate", "per", "trend", "delta", "change", "min", "minute", "sec", "second", "slope", "velocity"}

    best_row = None
    best_score = 0
    for row in rows:
        if row is current_row:
            continue

        row_tokens = set(_tokenize(" ".join([str(row.get("field_path", "")), str(row.get("label", "")), str(row.get("field_key", ""))])))
        if "co2" not in row_tokens and "pressure" not in row_tokens and not (row_tokens & base_tokens):
            continue

        if not (row_tokens & rate_keywords):
            continue

        score = len(row_tokens & base_tokens) + len(row_tokens & rate_keywords)
        if score > best_score:
            best_score = score
            best_row = row

    return best_row


def _find_consumption_row(rows: List[Dict[str, Any]], current_row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    current_field_path = str(current_row.get("field_path", "")).lower()
    current_label = str(current_row.get("label", "")).lower()
    current_key = str(current_row.get("field_key", "")).lower()
    base_tokens = set(_tokenize(" ".join([current_field_path, current_label, current_key])))

    consumption_keywords = {"consumption", "consuming", "consume", "usage", "use", "draw", "rate", "per", "minute", "second"}
    best_row = None
    best_score = 0

    for row in rows:
        if row is current_row:
            continue

        row_tokens = set(_tokenize(" ".join([str(row.get("field_path", "")), str(row.get("label", "")), str(row.get("field_key", ""))])))
        if not (row_tokens & consumption_keywords or "consumption" in row_tokens):
            continue

        # Prefer rows tied to oxygen/consumption, even when the row doesn't repeat the storage phrase.
        if not ((row_tokens & base_tokens) or {"o2", "oxygen", "oxy", "consumption"} & row_tokens):
            continue

        score = len(row_tokens & base_tokens) + len(row_tokens & consumption_keywords)
        if score > best_score:
            best_score = score
            best_row = row

    return best_row


def _format_duration(seconds: float) -> str:
    if seconds < 0:
        seconds = abs(seconds)

    total_seconds = int(round(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    parts: List[str] = []
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if not parts:
        parts.append(f"{secs} second{'s' if secs != 1 else ''}")
    return " ".join(parts)


def _build_time_answer(row: Dict[str, Any], label_text: str, seconds: float) -> TelemetryAnswer:
    return TelemetryAnswer(
        float(seconds),
        "seconds",
        label_text,
        _extract_entity_label(str(row.get("field_path", ""))),
        str(row.get("field_path", "")),
        "time",
    )


def _row_label_text(row: Dict[str, Any]) -> str:
    return _clean_label(str(row.get("label", "")), str(row.get("field_key", ""))).lower()


def _match_field_rows(question: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized_question = _normalize_question(question)
    question_tokens = _tokenize(normalized_question)
    aliases = _field_aliases()
    matched_rows: List[Dict[str, Any]] = []

    for row in rows:
        if _question_matches_field(question, row):
            matched_rows.append(row)

    # Keep the strongest matches only.
    if matched_rows:
        # Filter by requested entity if specified
        requested_entity = _extract_requested_entity(question)
        entity_filtered = _filter_rows_by_entity(matched_rows, requested_entity)
        
        scored = [(_score_row(question_tokens, row), row) for row in entity_filtered]
        best_score = max(score for score, _ in scored)
        top_rows = [row for score, row in scored if score == best_score]

        # Prefer rows that have a numeric value and the most explicit field name.
        if len(top_rows) > 1:
            numeric_rows = [row for row in top_rows if _extract_numeric_value(row.get("value")) is not None]
            if numeric_rows:
                top_rows = numeric_rows

            top_rows.sort(key=lambda row: len(str(row.get("field_path", ""))))
            return [top_rows[0]]

        return top_rows

    return []


def _extract_value_kind(row: Dict[str, Any]) -> str:
    unit = str(row.get("unit", "")).strip().lower()
    value = row.get("value")
    field_key = str(row.get("field_key", "")).lower()

    if isinstance(value, bool):
        return "bool"
    if unit == "%" or "percent" in field_key or "percentage" in field_key:
        return "percent"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    return "string"


def _coerce_typed_value(value: Any, kind: str) -> Any:
    if kind in {"percent", "float", "int"}:
        numeric_value = _extract_numeric_value(value)
        if numeric_value is None:
            return None
        if kind == "int" and float(numeric_value).is_integer():
            return int(numeric_value)
        return float(numeric_value)

    if kind == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "yes", "on", "1"}:
                return True
            if normalized in {"false", "no", "off", "0"}:
                return False
        return None

    return value if value is not None else None


def answer_question_with_code(question: str, telemetry_data: Dict[str, Any]) -> str:
    answer, _ = resolve_question(question, telemetry_data)
    return format_answer(answer)


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


def _filter_rows_by_entity(rows: List[Dict[str, Any]], entity: str) -> List[Dict[str, Any]]:
    """Filter rows to match the specified entity (eva1 or eva2)."""
    if not entity:
        return rows
    
    entity_lower = entity.lower()
    filtered = [row for row in rows if entity_lower in str(row.get("field_path", "")).lower()]
    return filtered if filtered else rows  # Return all if none match


def resolve_question(question: str, telemetry_data: Dict[str, Any]) -> Tuple[TelemetryAnswer, List[Dict[str, Any]]]:
    rows = _flatten_telemetry(telemetry_data)
    matched_rows = _find_direct_matches(question, rows)
    if not matched_rows:
        matched_rows = _match_field_rows(question, rows)

    if not matched_rows:
        return TelemetryAnswer(None, "", "", "UNKNOWN", "", "unknown"), []

    q = _normalize_question(question)

    # Special handling for coordinate questions - return both x and y if not specified
    if ("coordinate" in q or "position" in q or "location" in q) and "x" not in q and "y" not in q and "heading" not in q:
        x_row = None
        y_row = None
        for row in matched_rows:
            field_key = str(row.get("field_key", "")).lower()
            if field_key == "posx":
                x_row = row
            elif field_key == "posy":
                y_row = row
        
        if x_row and y_row:
            x_val = _extract_numeric_value(x_row.get("value"))
            y_val = _extract_numeric_value(y_row.get("value"))
            entity = _extract_entity_label(str(x_row.get("field_path", "")))
            
            if x_val is not None and y_val is not None:
                coord_str = f"({x_val}, {y_val})"
                return (
                    TelemetryAnswer(
                        coord_str,
                        "m",
                        "coordinates",
                        entity,
                        f"{x_row.get('field_path')} / {y_row.get('field_path')}",
                        "string",
                    ),
                    matched_rows,
                )

    if _is_time_to_threshold_question(question):
        current_row = matched_rows[0]
        current_value = _extract_numeric_value(current_row.get("value"))
        if current_value is None:
            return _build_time_answer(current_row, _row_label_text(current_row), 0.0), matched_rows

        rate_row = _find_consumption_row(rows, current_row) if _is_depletion_question(question) else _find_rate_row(rows, current_row)
        if rate_row is None:
            return _build_time_answer(current_row, _row_label_text(current_row), 0.0), matched_rows

        rate_value = _extract_numeric_value(rate_row.get("value"))
        if rate_value is None or rate_value == 0:
            return _build_time_answer(current_row, _row_label_text(current_row), 0.0), matched_rows

        rate_value = abs(rate_value)

        # If the telemetry exposes a maximum threshold, compute the remaining time.
        max_value = None
        for row in rows:
            row_tokens = set(_tokenize(" ".join([str(row.get("field_path", "")), str(row.get("label", "")), str(row.get("field_key", ""))])))
            if {"max", "maximum", "limit", "threshold"} & row_tokens and {"co2", "pressure"} & row_tokens:
                max_value = _extract_numeric_value(row.get("value"))
                if max_value is not None:
                    break

        if max_value is not None and max_value > current_value:
            remaining = max_value - current_value
            time_remaining = remaining / rate_value
            answer_label = f"time until {_row_label_text(current_row)} reaches maximum"
        else:
            if current_value <= 0:
                return _build_time_answer(current_row, _row_label_text(current_row), 0.0), matched_rows

            remaining = current_value
            time_remaining = remaining / rate_value
            answer_label = f"time until {_row_label_text(current_row)} is empty"

        return (
            _build_time_answer(current_row, answer_label, time_remaining),
            matched_rows,
        )

    # Basic arithmetic support: sum / total / average / difference / minus.
    numeric_values: List[float] = []
    for row in matched_rows:
        numeric_value = _extract_numeric_value(row.get("value"))
        if numeric_value is not None:
            numeric_values.append(numeric_value)

    if not numeric_values:
        first_row = matched_rows[0]
        field_key = str(first_row.get("field_key", ""))
        return (
            TelemetryAnswer(
                None,
                str(first_row.get("unit", "")),
                _clean_label(str(first_row.get("label", "")), field_key),
                _extract_entity_label(str(first_row.get("field_path", ""))),
                str(first_row.get("field_path", "")),
                _extract_value_kind(first_row),
            ),
            matched_rows,
        )

    if any(keyword in q for keyword in ["average", "mean"]):
        result = sum(numeric_values) / len(numeric_values)
    elif any(keyword in q for keyword in ["total", "sum", "add", "combined"]):
        result = sum(numeric_values)
    elif any(keyword in q for keyword in ["difference", "minus", "subtract"]):
        result = numeric_values[0] - sum(numeric_values[1:])
    else:
        # Default to the strongest single match.
        result = numeric_values[0]

    best_row = matched_rows[0]
    field_key = str(best_row.get("field_key", ""))
    kind = _extract_value_kind(best_row)
    if kind == "int" and float(result).is_integer():
        typed_value: Any = int(result)
    else:
        typed_value = float(result)

    return (
        TelemetryAnswer(
            typed_value,
            str(best_row.get("unit", "")),
            _clean_label(str(best_row.get("label", "")), field_key),
            _extract_entity_label(str(best_row.get("field_path", ""))),
            str(best_row.get("field_path", "")),
            kind,
        ),
        matched_rows,
    )


def _format_numeric_value(value: Any) -> str:
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return format(value, "g")
    return str(value)


def _extract_numeric_from_text(text: str) -> Optional[float]:
    """Extract numeric value from formatted text (e.g., '47%' -> 47.0)."""
    import re
    match = re.search(r'-?\d+\.?\d*', text)
    if match:
        try:
            return float(match.group())
        except ValueError:
            return None
    return None


def _validate_numeric_guardrail(original_value: Any, llm_response: str) -> bool:
    """Check that LLM response preserves the numeric value (with tolerance for formatting)."""
    if original_value is None:
        return True  # No value to validate
    
    original_numeric = _extract_numeric_value(original_value)
    if original_numeric is None:
        return True  # Non-numeric, can't validate
    
    llm_numeric = _extract_numeric_from_text(llm_response)
    if llm_numeric is None:
        return False  # LLM response has no numeric value; suspicious
    
    # Allow 1% tolerance for floating-point differences
    tolerance = max(abs(original_numeric * 0.01), 0.1)
    return abs(original_numeric - llm_numeric) <= tolerance


def _format_answer_with_llm(answer: TelemetryAnswer, question: str) -> str:
    """
    Format answer using LLM if available, with guardrails to preserve numeric value.
    Falls back to deterministic formatting if LLM unavailable or guardrail fails.
    """
    if not LLM_AVAILABLE:
        # LLM not installed; use default formatting
        return format_answer(answer)
    
    if answer.value is None:
        return format_answer(answer)  # Can't format None values
    
    # Get the deterministic baseline answer
    baseline_answer = format_answer(answer)
    
    try:
        # Initialize Ollama LLM (uses llama2 by default, adjust model as needed)
        llm = Ollama(
            model="llama2",
            callback_manager=CallbackManager([StreamingStdOutCallbackHandler()]),
            temperature=0.3,  # Low temperature for consistency
        )
        
        # Build context for the LLM
        value_text = _format_numeric_value(answer.value)
        if answer.kind == "percent" and not value_text.endswith("%"):
            value_text = f"{value_text}%"
        elif answer.unit and answer.unit != "unknown":
            if answer.unit not in {"%", "bpm", "psi"}:
                value_text = f"{value_text} {answer.unit}"
        
        prompt = f"""You are a concise voice assistant for a lunar spacesuit. Rewrite the following answer in natural, clear language for the astronaut. 
Keep it brief (1-2 sentences). DO NOT CHANGE the numeric values.

Original answer: {baseline_answer}
Question asked: {question}
Key fact: {answer.label} for {answer.entity} is {value_text}.

Rewrite (natural, concise, numeric values preserved):"""
        
        llm_response = llm.invoke(prompt).strip()
        
        # Apply guardrail: verify numeric value is preserved
        if _validate_numeric_guardrail(answer.value, llm_response):
            logger.info("LLM formatter accepted response (guardrail passed)")
            return llm_response
        else:
            logger.warning("LLM response failed numeric guardrail; falling back to deterministic format")
            return baseline_answer
    
    except Exception as e:
        logger.warning(f"LLM formatting failed ({e}); falling back to deterministic format")
        return baseline_answer


def format_answer(answer: TelemetryAnswer) -> str:
    if answer.value is None:
        return "not provided"

    if answer.kind == "time":
        duration_text = _format_duration(float(answer.value))
        if answer.entity != "UNKNOWN":
            return f"{answer.entity} {answer.label} is {duration_text}."
        return f"{answer.label.capitalize()} is {duration_text}."

    value_text = _format_numeric_value(answer.value)
    if answer.kind == "percent" and not value_text.endswith("%"):
        value_text = f"{value_text}%"
    elif answer.unit and answer.unit != "unknown" and not value_text.endswith(answer.unit):
        value_text = f"{value_text} {answer.unit}" if answer.unit not in {"%", "bpm", "psi"} else value_text

    label_text = answer.label.strip().lower()
    if label_text == "battery":
        label_text = "battery level"
    if label_text and answer.entity != "UNKNOWN":
        return f"{answer.entity} {label_text} is {value_text}."
    if label_text:
        return f"{label_text.capitalize()} is {value_text}."

    if answer.entity != "UNKNOWN":
        return f"{answer.entity} value is {value_text}."
    return f"Value is {value_text}."


def build_question_context(question: str, telemetry_data: Dict[str, Any]) -> str:
    rows = _flatten_telemetry(telemetry_data)
    relevant_rows = select_relevant_rows(question, rows)

    logger.info(
        "Prepared %s structured telemetry fields for LLM (%s relevant rows)",
        len(rows),
        len(relevant_rows),
    )

    return json.dumps(relevant_rows, indent=2, sort_keys=True)


# Chat history
chat_history = []

# Main loop
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("EVA Assistant (Live Telemetry Mode)")
    print("=" * 60)

    # Start background polling
    print("\nInitializing telemetry polling...")
    if not start_polling():
        print("ERROR: Could not start telemetry polling. Exiting.")
        exit(1)

    print("Telemetry polling active (updates every 1 second)\n")

    # Question loop
    while True:
        print("=" * 60)
        question = input("Ask your question (q to quit): ").strip()
        print()

        if question.lower() == "q":
            print("Exiting assistant. Goodbye!")
            break

        if not question:
            print("Please enter a question.")
            continue

        try:
            telemetry_data = get_current_telemetry()
            if not telemetry_data:
                print("ERROR: No telemetry data available\n")
                continue

            telemetry_context = build_question_context(question, telemetry_data)
            if telemetry_context == "[]":
                print("Assistant: not provided\n")
                continue

            logger.info("Processing question: %s", question)
            result, matched_rows = resolve_question(question, telemetry_data)
            result_text = _format_answer_with_llm(result, question)

            chat_history.append({"question": question, "answer": result_text})
            if len(chat_history) > MAX_HISTORY_TURNS:
                chat_history = chat_history[-MAX_HISTORY_TURNS:]

            print(f"Assistant: {result_text}\n")

        except Exception as e:
            logger.error("Error processing question: %s", e)
            print(f"ERROR: {e}\n")
