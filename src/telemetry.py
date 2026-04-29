"""
Simple telemetry data fetcher from HTTP Server.
No vector database, no embeddings—just raw data access.
Fetches data every second in background thread.
"""

import json
import logging
import os
import threading
import time
from typing import Any, Dict, Optional

import requests
from thresholds import THRESHOLDS, UNITS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
TELEMETRY_SERVER_BASE = os.getenv("TELEMETRY_SERVER_BASE", "http://172.18.0.1:14141")
TELEMETRY_FILES = ["EVA.json", "ROVER.json", "LTV.json"]
POLL_INTERVAL_SECONDS = 1  # Fetch every second like frontend

# Global state
_current_telemetry = None
_polling_thread = None
_polling_active = False
_lock = threading.Lock()


def fetch_telemetry_data() -> Optional[Dict[str, Any]]:
    """
    Fetch all telemetry data from server.

    Returns:
        dict: Merged telemetry from all JSON files, or None if fetch fails
    """
    snapshot = {}
    any_success = False

    for file_name in TELEMETRY_FILES:
        url = f"{TELEMETRY_SERVER_BASE}/data/{file_name}"
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()

            # Keep each source file separate so values do not overwrite one another.
            snapshot[file_name] = data

            any_success = True

        except requests.RequestException as e:
            logger.warning(f"Failed to fetch {file_name}: {e}")
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in {file_name}: {e}")

    return snapshot if any_success else None


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


def _flatten_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten a nested telemetry snapshot into simple key -> value map.

    Uses dotted keys for nested objects (e.g., 'EVA.json.eva1.primary_battery_level').
    """
    flat = {}
    for section, content in (snapshot or {}).items():
        prefix = section.replace('.json', '')
        if isinstance(content, dict):
            for k, v in content.items():
                if isinstance(v, dict):
                    for subk, subv in v.items():
                        flat_key = f"{prefix}.{k}.{subk}"
                        flat[flat_key] = subv
                else:
                    flat_key = f"{prefix}.{k}"
                    flat[flat_key] = v
        else:
            flat[prefix] = content
    return flat


def check_telemetry_thresholds(snapshot: Dict[str, Any]) -> Dict[str, list]:
    """Check snapshot against `THRESHOLDS` and return violations.

    Returns a dict with keys: 'below_min', 'above_max', each a list of messages.
    """
    below = []
    above = []

    flat = _flatten_snapshot(snapshot)

    # For each known threshold field, search for matching keys in the flattened
    # snapshot. Matching is simple containment: field name in flattened key.
    for field, (min_v, max_v) in THRESHOLDS.items():
        for k, v in flat.items():
            try:
                if field in k and isinstance(v, (int, float)):
                    if min_v is not None and v < min_v:
                        below.append(f"{k}={v} {UNITS.get(field,'') or ''} < min {min_v}")
                    if max_v is not None and v > max_v:
                        above.append(f"{k}={v} {UNITS.get(field,'') or ''} > max {max_v}")
            except Exception:
                # Defensive: ignore non-comparable values
                continue

    return {"below_min": below, "above_max": above}


def verify_units_present(snapshot: Dict[str, Any]) -> list:
    """Return a list of flattened keys that don't have a known unit mapping."""
    missing = []
    flat = _flatten_snapshot(snapshot)
    for k in flat.keys():
        # strip prefixes and look for a matching unit key
        # e.g., 'EVA.eva1.primary_battery_level' -> 'primary_battery_level'
        parts = k.split('.')
        # take last two parts if last part looks like a field name
        candidates = [parts[-1]] + (parts[-2:] if len(parts) >= 2 else [])
        found = False
        for c in candidates:
            if c in UNITS:
                found = True
                break
        if not found:
            missing.append(k)
    return missing
