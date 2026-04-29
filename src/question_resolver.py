"""
Question resolution logic: telemetry flattening, field matching, arithmetic, and time calculations.
Returns typed TelemetryAnswer objects with verified numeric values.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from field_routing import (
    FIELD_METADATA,
    _clean_label,
    _extract_entity_label,
    _extract_requested_entity,
    _field_aliases,
    _filter_rows_by_entity,
    _find_direct_matches,
    _normalize_question,
    _question_matches_field,
    _row_tokens,
    _score_row,
    _tokenize,
)

logger = logging.getLogger(__name__)


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


def answer_question_with_code(question: str, telemetry_data: Dict[str, Any]) -> str:
    from answer_formatter import format_answer
    answer, _ = resolve_question(question, telemetry_data)
    return format_answer(answer)
