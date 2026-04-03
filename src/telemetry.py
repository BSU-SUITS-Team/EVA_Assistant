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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
TELEMETRY_SERVER_BASE = os.getenv("TELEMETRY_SERVER_BASE", "http://192.168.0.11:14141")
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
    merged_data = {}
    any_success = False
    
    for file_name in TELEMETRY_FILES:
        url = f"{TELEMETRY_SERVER_BASE}/data/{file_name}"
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            # Merge sections
            for section, content in data.items():
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
        bool: True if started successfully, False if already running
    """
    global _polling_thread, _polling_active, _current_telemetry
    
    if _polling_active:
        logger.warning("Polling thread already running")
        return False
    
    # Fetch once immediately
    logger.info("Fetching initial telemetry...")
    _current_telemetry = fetch_telemetry_data()
    
    if not _current_telemetry:
        logger.error("Failed to fetch initial telemetry")
        return False
    
    logger.info("✓ Initial telemetry loaded")
    
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
