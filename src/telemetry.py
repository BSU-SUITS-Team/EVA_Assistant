"""
Simple telemetry data fetcher from HTTP Server.
No vector database, no embeddings—just raw data access.
Fetches data every second in background thread.
"""

import json
import requests
from typing import Optional, Dict, Any
import os
import logging
import threading
import time
import math
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
TELEMETRY_SERVER_BASE = os.getenv("TELEMETRY_SERVER_BASE", "http://172.17.0.1:14141")
TELEMETRY_FILES = ["EVA.json", "ROVER.json", "LTV.json"]
POLL_INTERVAL_SECONDS = 1  # Fetch every second like frontend
MAX_TELEMETRY_AGE_SECONDS = float(os.getenv("MAX_TELEMETRY_AGE_SECONDS", "10"))

# Lightweight schema guardrails for known top-level headings.
KNOWN_TOP_LEVEL_SECTIONS = {"telemetry", "dcu", "imu", "error", "uia"}
CRITICAL_NUMERIC_RANGES = {
    "oxy_pri_storage": (0.0, 100.0),
    "oxy_sec_storage": (0.0, 100.0),
    "battery": (0.0, 100.0),
    "heart_rate": (0.0, 220.0),
    "suit_pressure": (0.0, 15.0),
}
TIMESTAMP_KEYS = {"timestamp", "ts", "generated_at", "time", "created_at"}

# Global state
_current_telemetry = None
_polling_thread = None
_polling_active = False
_lock = threading.Lock()


def _is_valid_leaf(value: Any) -> bool:
    """Allow scalar JSON-compatible values and reject non-finite floats."""
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, str)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    return False


def _parse_timestamp(value: Any) -> Optional[float]:
    """Convert common timestamp formats to unix epoch seconds."""
    if isinstance(value, (int, float)):
        ts = float(value)
        # Handle millisecond epoch values.
        if ts > 1e12:
            ts = ts / 1000.0
        return ts

    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        try:
            if normalized.endswith("Z"):
                normalized = normalized[:-1] + "+00:00"
            dt = datetime.fromisoformat(normalized)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except ValueError:
            return None

    return None


def _find_timestamp(payload: Dict[str, Any]) -> Optional[float]:
    """Find a timestamp in common root-level metadata keys."""
    for key in TIMESTAMP_KEYS:
        if key in payload:
            parsed = _parse_timestamp(payload[key])
            if parsed is not None:
                return parsed
    return None


def _validate_section_dict(content: Dict[str, Any], section: str, file_name: str) -> Dict[str, Any]:
    """Validate one top-level section and return sanitized data."""
    sanitized: Dict[str, Any] = {}

    for key, value in content.items():
        path = f"{section}.{key}"

        if isinstance(value, dict):
            nested: Dict[str, Any] = {}
            for subkey, subvalue in value.items():
                nested_path = f"{path}.{subkey}"

                if isinstance(subvalue, dict):
                    logger.warning(
                        "Validation warning in %s: nested object too deep at %s; skipping",
                        file_name,
                        nested_path,
                    )
                    continue

                if not _is_valid_leaf(subvalue):
                    logger.warning(
                        "Validation warning in %s: invalid value type at %s (%s); skipping",
                        file_name,
                        nested_path,
                        type(subvalue).__name__,
                    )
                    continue

                if subkey in CRITICAL_NUMERIC_RANGES and isinstance(subvalue, (int, float)):
                    min_value, max_value = CRITICAL_NUMERIC_RANGES[subkey]
                    if not (min_value <= float(subvalue) <= max_value):
                        logger.warning(
                            "Validation warning in %s: out-of-range %s=%s (expected %s-%s); skipping",
                            file_name,
                            nested_path,
                            subvalue,
                            min_value,
                            max_value,
                        )
                        continue

                nested[subkey] = subvalue

            sanitized[key] = nested
            continue

        if not _is_valid_leaf(value):
            logger.warning(
                "Validation warning in %s: invalid value type at %s (%s); skipping",
                file_name,
                path,
                type(value).__name__,
            )
            continue

        if key in CRITICAL_NUMERIC_RANGES and isinstance(value, (int, float)):
            min_value, max_value = CRITICAL_NUMERIC_RANGES[key]
            if not (min_value <= float(value) <= max_value):
                logger.warning(
                    "Validation warning in %s: out-of-range %s=%s (expected %s-%s); skipping",
                    file_name,
                    path,
                    value,
                    min_value,
                    max_value,
                )
                continue

        sanitized[key] = value

    return sanitized


def validate_payload(file_name: str, payload: Dict[str, Any], fetched_at_utc: float) -> Dict[str, Any]:
    """
    Validate payload shape and field values and return sanitized telemetry.

    Validation strategy:
    - Allow known sections only
    - Require section values to be dictionaries
    - Allow only scalar leaves (no arbitrarily deep nested objects)
    - Enforce range checks for known critical numeric fields
    - Optionally reject stale payloads when a source timestamp exists
    """
    if not isinstance(payload, dict):
        logger.warning("Validation warning in %s: root payload must be an object; skipping", file_name)
        return {}

    payload_timestamp = _find_timestamp(payload)
    if payload_timestamp is not None:
        age_seconds = fetched_at_utc - payload_timestamp
        if age_seconds > MAX_TELEMETRY_AGE_SECONDS:
            logger.warning(
                "Validation warning in %s: stale payload age %.2fs (> %.2fs); skipping file",
                file_name,
                age_seconds,
                MAX_TELEMETRY_AGE_SECONDS,
            )
            return {}

    validated: Dict[str, Any] = {}

    for section, content in payload.items():
        if section in TIMESTAMP_KEYS:
            # Metadata is used for freshness checks only and excluded from telemetry payload.
            continue

        if section not in KNOWN_TOP_LEVEL_SECTIONS:
            logger.warning("Validation warning in %s: unknown section '%s'; skipping", file_name, section)
            continue

        if not isinstance(content, dict):
            logger.warning(
                "Validation warning in %s: section '%s' must be an object; skipping",
                file_name,
                section,
            )
            continue

        validated[section] = _validate_section_dict(content, section, file_name)

    return validated


def fetch_telemetry_data() -> Optional[Dict[str, Any]]:
    """
    Fetch all telemetry data from server.
    
    Returns:
        dict: Merged telemetry from all JSON files, or None if fetch fails
    """
    merged_data = {}
    any_success = False
    
    for file_name in TELEMETRY_FILES:
        url = f"{TELEMETRY_SERVER_BASE}/data/{file_name}"
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            fetched_at_utc = time.time()

            validated_data = validate_payload(file_name, data, fetched_at_utc)
            if not validated_data:
                logger.warning(f"No valid telemetry sections in {file_name}; skipping file")
                continue

            # Merge validated sections only.
            for section, content in validated_data.items():
                if section not in merged_data:
                    merged_data[section] = {}
                if isinstance(content, dict):
                    merged_data[section].update(content)
                else:
                    merged_data[section] = content
            
            any_success = True
            
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch {file_name}: {e}")
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in {file_name}: {e}")
    
    return merged_data if any_success else None


def get_current_telemetry() -> Optional[Dict[str, Any]]:
    """
    Get the most recently fetched telemetry data.
    Thread-safe access to current data.
    """
    with _lock:
        return _current_telemetry


def _polling_loop():
    """Background thread that fetches telemetry every second."""
    global _current_telemetry, _polling_active
    
    _polling_active = True
    logger.info(f"Starting telemetry polling thread (interval: {POLL_INTERVAL_SECONDS}s)")
    
    while _polling_active:
        try:
            data = fetch_telemetry_data()
            if data:
                with _lock:
                    _current_telemetry = data
                logger.debug(f"Telemetry updated ({len(data)} sections)")
            else:
                logger.warning("Failed to fetch telemetry in polling loop")
        except Exception as e:
            logger.error(f"Polling error: {e}")
        
        time.sleep(POLL_INTERVAL_SECONDS)


def start_polling() -> bool:
    """
    Start background thread to poll telemetry every second.
    
    Returns:
        bool: True if polling is active, False if already running
    """
    global _polling_thread, _polling_active, _current_telemetry
    
    if _polling_active:
        logger.warning("Polling thread already running")
        return False
    
    # Fetch once immediately, but do not treat failure as fatal.
    logger.info("Fetching initial telemetry...")
    _current_telemetry = fetch_telemetry_data()

    if _current_telemetry:
        logger.info("✓ Initial telemetry loaded")
    else:
        logger.warning("Initial telemetry unavailable; continuing to poll in background")
    
    # Start background thread
    _polling_thread = threading.Thread(target=_polling_loop, daemon=True)
    _polling_thread.start()
    
    return True


def stop_polling():
    """Stop background polling thread."""
    global _polling_active
    if _polling_active:
        _polling_active = False
        logger.info("Polling thread stopped")


def format_telemetry_for_llm(data: Dict[str, Any]) -> str:
    """
    Format telemetry data as readable text for LLM.
    
    Args:
        data: Merged telemetry dictionary
    
    Returns:
        str: Formatted telemetry text
    """
    if not data:
        return "No telemetry data available."
    
    lines = []
    lines.append("=== TELEMETRY DATA ===\n")
    
    # Format each section
    for section, content in data.items():
        if isinstance(content, dict):
            lines.append(f"\n[{section.upper()}]")
            for key, value in content.items():
                if isinstance(value, dict):
                    # Nested dict (e.g., eva1, eva2)
                    for subkey, subvalue in value.items():
                        lines.append(f"  {key}.{subkey}: {subvalue}")
                else:
                    lines.append(f"  {key}: {value}")
        else:
            lines.append(f"\n[{section.upper()}]: {content}")
    
    return "\n".join(lines)
