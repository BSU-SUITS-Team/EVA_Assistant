"""
Mission procedures database: hardcoded, verified procedure sequences.
Procedures are mission-critical and should NOT be LLM-generated.
Source: NASA SUITS Mission Description, Appendix A.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass(frozen=True)
class ProcedureStep:
    """Single step in a procedure."""
    number: int
    action: str  # What to do/check
    target: str  # Where (UIA, HMD, DCU BOTH, etc.)
    wait_condition: Optional[str] = None  # What to wait for (e.g., "until Primary O2 > 3000 psi")
    notes: Optional[str] = None  # Additional context


@dataclass(frozen=True)
class Procedure:
    """A complete procedure sequence."""
    name: str
    description: str
    steps: List[ProcedureStep]
    mission_phase: str  # "egress", "eva", "ingress", "repair", etc.


# UIA (Umbilical Interface Assembly) Egress Procedures
# From NASA SUITS Mission Description Appendix A
UIA_EGRESS_PROCEDURES = Procedure(
    name="UIA Egress",
    description="EVA egress preparation: Connect UIA, depressurize, prep O2 tanks, final checks",
    mission_phase="egress",
    steps=[
        # Phase 1: Connect and Depress
        ProcedureStep(
            number=1,
            action="Verify umbilical connection from UIA to DCU",
            target="UIA and DCU",
        ),
        ProcedureStep(
            number=2,
            action="EMU PWR – ON",
            target="UIA",
        ),
        ProcedureStep(
            number=3,
            action="BATT – UMB",
            target="DCU",
        ),
        ProcedureStep(
            number=4,
            action="DEPRESS PUMP PWR – ON",
            target="UIA",
        ),
        # Phase 2: Prep O2 Tanks
        ProcedureStep(
            number=5,
            action="OXYGEN O2 VENT – OPEN",
            target="UIA",
        ),
        ProcedureStep(
            number=6,
            action="Wait until both Primary and Secondary OXY tanks are < 10psi",
            target="HMD",
            wait_condition="both O2 tanks < 10psi",
        ),
        ProcedureStep(
            number=7,
            action="OXYGEN O2 VENT – CLOSE",
            target="UIA",
        ),
        ProcedureStep(
            number=8,
            action="OXY – PRI",
            target="BOTH DCU",
        ),
        ProcedureStep(
            number=9,
            action="OXYGEN EMU-1 – OPEN",
            target="UIA",
        ),
        ProcedureStep(
            number=10,
            action="Wait until EV1 Primary O2 tank > 3000 psi",
            target="HMD",
            wait_condition="Primary O2 tank > 3000 psi",
        ),
        ProcedureStep(
            number=11,
            action="OXYGEN EMU-1 – CLOSE",
            target="UIA",
        ),
        ProcedureStep(
            number=12,
            action="OXY – SEC",
            target="BOTH DCU",
        ),
        ProcedureStep(
            number=13,
            action="OXYGEN EMU-1 – OPEN",
            target="UIA",
        ),
        ProcedureStep(
            number=14,
            action="Wait until EV1 Secondary O2 tank > 3000 psi",
            target="HMD",
            wait_condition="Secondary O2 tank > 3000 psi",
        ),
        ProcedureStep(
            number=15,
            action="OXYGEN EMU-1 – CLOSE",
            target="UIA",
        ),
        ProcedureStep(
            number=16,
            action="OXY – PRI",
            target="BOTH DCU",
        ),
        # Phase 3: Final Checks and Disconnect
        ProcedureStep(
            number=17,
            action="Wait until SUIT Pressure, O2 Pressure = 4",
            target="HMD",
            wait_condition="SUIT pressure and O2 pressure both at 4 psi",
        ),
        ProcedureStep(
            number=18,
            action="DEPRESS PUMP PWR – OFF",
            target="UIA",
        ),
        ProcedureStep(
            number=19,
            action="BATT – LOCAL",
            target="BOTH DCU",
        ),
        ProcedureStep(
            number=20,
            action="EV-1 EMU PWR - OFF",
            target="UIA",
        ),
        ProcedureStep(
            number=21,
            action="Verify OXY – PRI",
            target="BOTH DCU",
        ),
        ProcedureStep(
            number=22,
            action="Verify COMMS – A",
            target="BOTH DCU",
        ),
        ProcedureStep(
            number=23,
            action="Verify FAN – PRI",
            target="BOTH DCU",
        ),
        ProcedureStep(
            number=24,
            action="Verify PUMP – CLOSE",
            target="BOTH DCU",
        ),
        ProcedureStep(
            number=25,
            action="Verify CO2 – A",
            target="BOTH DCU",
        ),
        ProcedureStep(
            number=26,
            action="EV1 disconnect UIA and DCU umbilical",
            target="UIA and DCU",
        ),
    ]
)

# Procedure database indexed by name
PROCEDURE_DATABASE: Dict[str, Procedure] = {
    "uia_egress": UIA_EGRESS_PROCEDURES,
    "egress": UIA_EGRESS_PROCEDURES,
    "eva egress": UIA_EGRESS_PROCEDURES,
}


def get_procedure(name: str) -> Optional[Procedure]:
    """Retrieve a procedure by name (case-insensitive)."""
    normalized = name.lower().strip().replace(" ", "_")
    return PROCEDURE_DATABASE.get(normalized)


def list_available_procedures() -> List[str]:
    """List all available procedure names."""
    return list(PROCEDURE_DATABASE.keys())


def is_procedure_request(question: str) -> bool:
    """Check if a question is asking for a procedure."""
    normalized = question.lower()
    procedure_keywords = {
        "procedure", "procedures", "steps", "step", "guide", "guidance",
        "checklist", "check list", "egress", "ingress", "repair", "how to",
        "walk through", "walkthrough", "instruction", "instructions"
    }
    return any(keyword in normalized for keyword in procedure_keywords)
