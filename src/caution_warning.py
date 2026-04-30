"""
Caution & Warning System for EVA telemetry monitoring.

Detects off-nominal values and recommends procedures/actions to address them.
Provides alerts formatted for natural language display.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple

from thresholds import THRESHOLDS, UNITS

logger = logging.getLogger(__name__)


class CautionWarning:
    """Alert for off-nominal telemetry."""
    
    def __init__(self, field: str, value: float, min_threshold: Optional[float], 
                 max_threshold: Optional[float], severity: str = "caution"):
        self.field = field
        self.value = value
        self.min = min_threshold
        self.max = max_threshold
        self.severity = severity  # "caution" or "warning"
        self.unit = UNITS.get(field, "")
    
    def format_alert(self) -> str:
        """Return human-readable alert message."""
        direction = "critically low" if self.min and self.value < self.min else "critically high"
        if self.severity == "caution":
            direction = direction.replace("critically ", "")
        
        formatted_value = f"{self.value:.1f}" if isinstance(self.value, float) else str(self.value)
        return f"{self.field.replace('_', ' ').title()}: {formatted_value}{self.unit} ({direction})"
    
    def __repr__(self) -> str:
        return f"CautionWarning({self.field}={self.value}, severity={self.severity})"


def detect_off_nominal_values(telemetry: Dict[str, Any]) -> List[CautionWarning]:
    """
    Scan telemetry for off-nominal values against defined thresholds.
    
    Args:
        telemetry: Current telemetry snapshot from server
    
    Returns:
        List of CautionWarning objects for detected issues
    """
    alerts = []
    
    # Flatten telemetry to find numeric fields
    def scan_dict(obj: Any, path: str = ""):
        if isinstance(obj, dict):
            for key, value in obj.items():
                new_path = f"{path}_{key}".lstrip("_") if path else key
                scan_dict(value, new_path)
        elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
            # Check against thresholds
            min_val, max_val = THRESHOLDS.get(path, (None, None))
            
            if min_val is not None and obj < min_val:
                severity = "warning" if obj < min_val * 0.5 else "caution"
                alerts.append(CautionWarning(path, obj, min_val, max_val, severity))
            elif max_val is not None and obj > max_val:
                severity = "warning" if obj > max_val * 1.5 else "caution"
                alerts.append(CautionWarning(path, obj, min_val, max_val, severity))
    
    scan_dict(telemetry)
    
    # Sort by severity (warnings first)
    alerts.sort(key=lambda a: ("warning" != a.severity))
    return alerts


def get_recommended_actions(alerts: List[CautionWarning]) -> Dict[str, str]:
    """
    Map alerts to recommended procedures/actions.
    
    Args:
        alerts: List of CautionWarning objects
    
    Returns:
        Dict mapping field name to recommended action text
    """
    recommendations = {}
    
    for alert in alerts:
        field = alert.field.lower()
        
        # O2-related alerts
        if "oxy_pri" in field and "pressure" in field and alert.value < alert.min:
            recommendations[alert.field] = (
                "Primary O2 pressure critically low. "
                "Recommend switching to secondary O2 or returning to base immediately."
            )
        elif "oxy_pri" in field and "storage" in field and alert.value < 20:
            recommendations[alert.field] = (
                "Primary O2 storage below 20%. "
                "Estimate remaining time and consider returning to base."
            )
        elif "oxy_sec" in field and "pressure" in field and alert.value < alert.min:
            recommendations[alert.field] = (
                "Secondary O2 pressure low. "
                "Begin return-to-base procedures."
            )
        
        # Battery alerts
        elif "battery" in field and alert.value < 20:
            recommendations[alert.field] = (
                "Battery level critically low. "
                "Conserve power and prepare for return to base."
            )
        
        # CO2/Fan alerts (indicate system malfunction)
        elif "fan" in field and alert.value == 0:
            recommendations[alert.field] = (
                "Fan failure detected. Request system diagnosis and proceed with caution."
            )
        
        # Pressure suit alerts
        elif "suit_pressure" in field and alert.value < 3.5:
            recommendations[alert.field] = (
                "Suit pressure below nominal range. Check for breach or equipment failure."
            )
        
        # Rover handling alerts
        elif "pitch" in field or "roll" in field or "incline" in field:
            if alert.value > 45.0:
                recommendations[alert.field] = (
                    "Extreme terrain slope detected. Slow down and adjust trajectory."
                )
        
        # Default fallback
        if alert.field not in recommendations:
            recommendations[alert.field] = (
                f"{alert.field.replace('_', ' ').title()} is at {alert.value} {alert.unit}. "
                "Monitor closely and consider requesting diagnostic support."
            )
    
    return recommendations


def format_caution_warning_report(alerts: List[CautionWarning]) -> Optional[str]:
    """
    Format alerts into a natural language report.
    
    Args:
        alerts: List of CautionWarning objects
    
    Returns:
        Formatted report string, or None if no alerts
    """
    if not alerts:
        return None
    
    warnings = [a for a in alerts if a.severity == "warning"]
    cautions = [a for a in alerts if a.severity == "caution"]
    
    lines = []
    
    if warnings:
        lines.append(f"⚠️  WARNINGS ({len(warnings)}):")
        for alert in warnings:
            lines.append(f"  • {alert.format_alert()}")
    
    if cautions:
        if warnings:
            lines.append("")
        lines.append(f"⚡ CAUTIONS ({len(cautions)}):")
        for alert in cautions:
            lines.append(f"  • {alert.format_alert()}")
    
    return "\n".join(lines)
