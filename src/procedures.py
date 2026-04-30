"""
Mission procedures database.

UIA egress remains local because it is the stable mission appendix source.
All LTV procedures are loaded at runtime from TSS `LTV_ERRORS.json` via
`procedure_store.py` and are not hard-coded here.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ProcedureStep:
    """Single step in a procedure."""
    number: int
    action: str
    target: str
    wait_condition: Optional[str] = None
    notes: Optional[str] = None


@dataclass(frozen=True)
class Procedure:
    """A complete procedure sequence."""
    name: str
    description: str
    steps: List[ProcedureStep]
    mission_phase: str


# UIA (Umbilical Interface Assembly) Egress Procedures
# From NASA SUITS Mission Description Appendix A
UIA_EGRESS_PROCEDURES = Procedure(
    name="UIA Egress",
    description="EVA egress preparation: Connect UIA, depressurize, prep O2 tanks, final checks",
    mission_phase="egress",
    steps=[
        ProcedureStep(number=1, action="Verify umbilical connection from UIA to DCU", target="UIA and DCU"),
        ProcedureStep(number=2, action="EMU PWR – ON", target="UIA"),
        ProcedureStep(number=3, action="BATT – UMB", target="DCU"),
        ProcedureStep(number=4, action="DEPRESS PUMP PWR – ON", target="UIA"),
        ProcedureStep(number=5, action="OXYGEN O2 VENT – OPEN", target="UIA"),
        ProcedureStep(number=6, action="Wait until both Primary and Secondary OXY tanks are < 10psi", target="HMD", wait_condition="both O2 tanks < 10psi"),
        ProcedureStep(number=7, action="OXYGEN O2 VENT – CLOSE", target="UIA"),
        ProcedureStep(number=8, action="OXY – PRI", target="BOTH DCU"),
        ProcedureStep(number=9, action="OXYGEN EMU-1 – OPEN", target="UIA"),
        ProcedureStep(number=10, action="Wait until EV1 Primary O2 tank > 3000 psi", target="HMD", wait_condition="Primary O2 tank > 3000 psi"),
        ProcedureStep(number=11, action="OXYGEN EMU-1 – CLOSE", target="UIA"),
        ProcedureStep(number=12, action="OXY – SEC", target="BOTH DCU"),
        ProcedureStep(number=13, action="OXYGEN EMU-1 – OPEN", target="UIA"),
        ProcedureStep(number=14, action="Wait until EV1 Secondary O2 tank > 3000 psi", target="HMD", wait_condition="Secondary O2 tank > 3000 psi"),
        ProcedureStep(number=15, action="OXYGEN EMU-1 – CLOSE", target="UIA"),
        ProcedureStep(number=16, action="OXY – PRI", target="BOTH DCU"),
        ProcedureStep(number=17, action="Wait until SUIT Pressure, O2 Pressure = 4", target="HMD", wait_condition="SUIT pressure and O2 pressure both at 4 psi"),
        ProcedureStep(number=18, action="DEPRESS PUMP PWR – OFF", target="UIA"),
        ProcedureStep(number=19, action="BATT – LOCAL", target="BOTH DCU"),
        ProcedureStep(number=20, action="EV-1 EMU PWR - OFF", target="UIA"),
        ProcedureStep(number=21, action="Verify OXY – PRI", target="BOTH DCU"),
        ProcedureStep(number=22, action="Verify COMMS – A", target="BOTH DCU"),
        ProcedureStep(number=23, action="Verify FAN – PRI", target="BOTH DCU"),
        ProcedureStep(number=24, action="Verify PUMP – CLOSE", target="BOTH DCU"),
        ProcedureStep(number=25, action="Verify CO2 – A", target="BOTH DCU"),
        ProcedureStep(number=26, action="EV1 disconnect UIA and DCU umbilical", target="UIA and DCU"),
    ],
)


PROCEDURE_DATABASE: Dict[str, Procedure] = {
    "uia_egress": UIA_EGRESS_PROCEDURES,
    "egress": UIA_EGRESS_PROCEDURES,
    "eva egress": UIA_EGRESS_PROCEDURES,
}


def _normalize_name(name: str) -> str:
    return "".join(char.lower() if char.isalnum() else "_" for char in name).strip("_")


def get_procedure(name: str) -> Optional[Procedure]:
    """Retrieve a procedure by name.

    UIA egress stays local. All LTV procedures are resolved dynamically from the
    TSS runtime store via `src/procedure_store.py`.
    """
    normalized = _normalize_name(name)
    local = PROCEDURE_DATABASE.get(normalized) or PROCEDURE_DATABASE.get(name.lower().strip())
    if local is not None:
        return local

    from procedure_store import get_procedure as get_runtime_procedure

    return get_runtime_procedure(name, requester="procedure_lookup")


def list_available_procedures() -> List[str]:
    """List local procedures plus any procedures discovered from TSS."""
    available = set(PROCEDURE_DATABASE.keys())

    try:
        from procedure_store import list_available_procedures as list_runtime_procedures

        available.update(_normalize_name(name) for name in list_runtime_procedures())
    except Exception:
        pass

    return sorted(available)


def is_procedure_request(question: str) -> bool:
    """Check if a question is asking for a procedure or error-code lookup."""
    normalized = question.lower()
    procedure_keywords = {
        "procedure", "procedures", "steps", "step", "guide", "guidance",
        "checklist", "check list", "egress", "ingress", "repair", "how to",
        "walk through", "walkthrough", "instruction", "instructions",
        "exit recovery", "erm", "erp", "diagnosis", "diagnose", "bus connector",
        "dust sensor", "sensor replacement", "verification", "verify",
        "error", "errors", "error code", "code", "codes", "troubleshoot", "troubleshooting",
    }
    return any(keyword in normalized for keyword in procedure_keywords)


# Error Code to Procedure mapping for automated recommendations
ERROR_PROCEDURE_MAP: Dict[str, Dict[str, str]] = {
    # Format: "error_code": {"description": "...", "action": "..."}
    "0000": {
        "description": "Recovery Mode",
        "action": "Exit Recovery Mode (ERM)",
        "severity": "critical",
    },
    "2129": {
        "description": "Backup Fuse Error",
        "action": "Replace fuses or diagnose power system",
        "severity": "critical",
    },
    "4155": {
        "description": "Main Power Bus Error",
        "action": "Reconnect loose bus connector or replace power cable",
        "severity": "critical",
    },
    "4761": {
        "description": "Dust Sensor Error",
        "action": "Replace dust sensor or perform diagnostics",
        "severity": "high",
    },
    "2235": {
        "description": "Dust Sensor Error",
        "action": "Replace dust sensor",
        "severity": "medium",
    },
    "3452": {
        "description": "Poor Comms RSSI",
        "action": "Adjust antenna or restart comms system",
        "severity": "medium",
    },
    "4280": {
        "description": "Small Fuse Box Error",
        "action": "Check scientific fuses and replace as needed",
        "severity": "medium",
    },
    "4509": {
        "description": "NAV Restart & Manual Return to Home",
        "action": "Restart navigation system and manual return to base",
        "severity": "high",
    },
    "4800": {
        "description": "Exit Recovery Mode (ERM)",
        "action": "Perform Exit Recovery Mode procedure",
        "severity": "critical",
    },
    "4968": {
        "description": "Subsystem Power Bus Error",
        "action": "Inspect and reconnect power cables",
        "severity": "high",
    },
    "2441": {
        "description": "Comms Reboot Required Error",
        "action": "Restart communications subsystem",
        "severity": "medium",
    },
}


def get_error_procedure(error_code: str) -> Optional[Dict[str, str]]:
    """Get procedure recommendation for an error code."""
    return ERROR_PROCEDURE_MAP.get(error_code)
