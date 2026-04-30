"""
Resource Analytics: Predictive depletion and consumption tracking.

Calculates time-to-empty for consumables (O2, battery, CO2) based on current
consumption rates and capacity levels. Provides natural language status updates.
"""

import logging
from typing import Dict, Optional, Tuple, Any

from thresholds import UNITS

logger = logging.getLogger(__name__)


class ResourceStatus:
    """Current status of a consumable resource."""
    
    def __init__(self, name: str, current_level: float, consumption_rate: float,
                 unit: str, min_safe_level: float = 10.0):
        self.name = name
        self.current_level = current_level  # % or psi
        self.consumption_rate = consumption_rate  # units per minute
        self.unit = unit
        self.min_safe_level = min_safe_level
    
    def time_to_depletion(self) -> Optional[float]:
        """Calculate minutes until resource depleted."""
        if self.consumption_rate <= 0:
            return None
        
        # Convert percentage to absolute if needed
        available = self.current_level - self.min_safe_level
        if available <= 0:
            return 0.0
        
        minutes = available / self.consumption_rate
        return max(0.0, minutes)
    
    def time_to_safe_level(self) -> Optional[float]:
        """Calculate minutes until safe minimum level reached."""
        if self.consumption_rate <= 0:
            return None
        
        return self.time_to_depletion()
    
    def status_text(self, include_rate: bool = True) -> str:
        """Return human-readable status."""
        ttd = self.time_to_depletion()
        
        if ttd is None or ttd <= 0:
            return f"{self.name}: {self.current_level:.1f}{self.unit} (depleted)"
        
        hours = int(ttd // 60)
        minutes = int(ttd % 60)
        time_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
        
        status = f"{self.name}: {self.current_level:.1f}{self.unit}, ~{time_str} remaining"
        
        if include_rate:
            status += f" (consuming {self.consumption_rate:.2f}{self.unit}/min)"
        
        return status
    
    def __repr__(self) -> str:
        return f"ResourceStatus({self.name}: {self.current_level}{self.unit} @ {self.consumption_rate}/min)"


def extract_eva_consumables(telemetry: Dict[str, Any]) -> Dict[str, ResourceStatus]:
    """
    Extract EVA consumable resource data from telemetry.
    
    Args:
        telemetry: Current telemetry snapshot
    
    Returns:
        Dict mapping resource name to ResourceStatus object
    """
    resources = {}
    
    # Navigate nested telemetry structure
    eva_data = telemetry.get("EVA.json", {})
    
    # Primary O2 - convert psi to % equivalent
    oxy_pri_pressure = eva_data.get("oxy_pri_pressure", 0)
    oxy_pri_storage = eva_data.get("oxy_pri_storage", 0)
    oxy_consumption = eva_data.get("oxy_consumption", 0.05)  # psi/min
    
    if oxy_pri_pressure > 0:
        # Normalize: 3000 psi = 100%
        oxy_pri_pct = (oxy_pri_pressure / 3000.0) * 100
        resources["O2 (Primary)"] = ResourceStatus(
            "O2 (Primary)",
            oxy_pri_pct,
            oxy_consumption,
            "%",
            min_safe_level=20.0  # 600 psi = 20%
        )
    
    # Secondary O2
    oxy_sec_pressure = eva_data.get("oxy_sec_pressure", 0)
    if oxy_sec_pressure > 0:
        oxy_sec_pct = (oxy_sec_pressure / 3000.0) * 100
        resources["O2 (Secondary)"] = ResourceStatus(
            "O2 (Secondary)",
            oxy_sec_pct,
            oxy_consumption,
            "%",
            min_safe_level=20.0
        )
    
    # Battery
    primary_battery = eva_data.get("primary_battery_level", 0)
    if primary_battery > 0:
        battery_consumption = 0.5  # Rough estimate: 1% per 2 minutes
        resources["Primary Battery"] = ResourceStatus(
            "Primary Battery",
            primary_battery,
            battery_consumption,
            "%",
            min_safe_level=20.0
        )
    
    secondary_battery = eva_data.get("secondary_battery_level", 0)
    if secondary_battery > 0:
        resources["Secondary Battery"] = ResourceStatus(
            "Secondary Battery",
            secondary_battery,
            battery_consumption,
            "%",
            min_safe_level=20.0
        )
    
    # CO2 cartridge (if available)
    co2_production = eva_data.get("co2_production", 0)
    if co2_production > 0:
        # Assume CO2 canister can handle ~10000 psi worth of CO2
        co2_level = eva_data.get("co2_cartridge_level", 100)
        resources["CO2 Cartridge"] = ResourceStatus(
            "CO2 Cartridge",
            co2_level,
            co2_production,
            "%",
            min_safe_level=10.0
        )
    
    return resources


def get_resource_summary(telemetry: Dict[str, Any], critical_only: bool = False) -> Optional[str]:
    """
    Get natural language summary of consumable resources.
    
    Args:
        telemetry: Current telemetry snapshot
        critical_only: If True, only report resources below 50%
    
    Returns:
        Formatted resource summary or None if no data
    """
    resources = extract_eva_consumables(telemetry)
    
    if not resources:
        return None
    
    lines = []
    criticals = []
    
    for name, status in sorted(resources.items()):
        if status.current_level < 50:
            criticals.append(status.status_text(include_rate=False))
        elif not critical_only:
            lines.append(status.status_text(include_rate=False))
    
    if criticals:
        lines.insert(0, "⚠️  CRITICAL RESOURCES:")
        lines.extend(["  • " + c for c in criticals])
    
    return "\n".join(lines) if lines else None


def estimate_return_time(telemetry: Dict[str, Any], distance_to_base: float) -> Optional[str]:
    """
    Estimate time to return to base given current speed and distance.
    
    Args:
        telemetry: Current telemetry snapshot
        distance_to_base: Distance in meters
    
    Returns:
        Formatted estimate or None if insufficient data
    """
    eva_data = telemetry.get("EVA.json", {})
    speed_mps = eva_data.get("speed", 0)  # meters per second
    
    if speed_mps <= 0:
        return None
    
    # Assume EVA move speed ~1 m/s on lunar terrain
    eva_speed = 1.0  # m/s, conservative for moon
    minutes = (distance_to_base / eva_speed) / 60
    
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    
    time_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
    return f"Estimated return time: ~{time_str} at {eva_speed} m/s"


def check_resource_criticality(telemetry: Dict[str, Any]) -> Optional[str]:
    """
    Check if any resources are critically low and need immediate action.
    
    Args:
        telemetry: Current telemetry snapshot
    
    Returns:
        Alert message if critical, None otherwise
    """
    resources = extract_eva_consumables(telemetry)
    
    criticals = []
    for name, status in resources.items():
        ttd = status.time_to_depletion()
        if ttd is not None and ttd < 15:  # Less than 15 minutes
            if ttd < 5:
                criticals.append(f"🚨 {name}: CRITICAL - {int(ttd)} minutes remaining")
            else:
                criticals.append(f"⚠️  {name}: Low - {int(ttd)} minutes remaining")
    
    return "\n".join(criticals) if criticals else None
