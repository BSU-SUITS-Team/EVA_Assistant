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

# LTV Repair Procedures
# From NASA SUITS Mission Description Section 2c (LTV Repair)

LTV_ERM_PROCEDURE = Procedure(
    name="LTV Exit Recovery Mode",
    description="Exit Recovery Mode (ERM) to restore LTV to operational state",
    mission_phase="repair",
    steps=[
        ProcedureStep(
            number=1,
            action="Retrieve ERM procedures from AI assistant (AIA)",
            target="Voice Assistant",
        ),
        ProcedureStep(
            number=2,
            action="Follow procedures provided by AIA",
            target="LTV",
            notes="Each step will be guided by the AI assistant",
        ),
        ProcedureStep(
            number=3,
            action="Wait for voice assistant/UI to announce ERM success",
            target="Voice Assistant / HMD",
            wait_condition="ERM success confirmation",
        ),
        ProcedureStep(
            number=4,
            action="Proceed to system diagnosis",
            target="Voice Assistant",
        ),
    ]
)

LTV_DIAGNOSIS_PROCEDURE = Procedure(
    name="LTV System Diagnosis",
    description="Perform system diagnosis to identify LTV malfunctions",
    mission_phase="repair",
    steps=[
        ProcedureStep(
            number=1,
            action="Command AIA to conduct system diagnosis",
            target="Voice Assistant",
            notes="Say 'Begin system diagnosis' when ready",
        ),
        ProcedureStep(
            number=2,
            action="Perform visual inspection to determine issues",
            target="EV",
            notes="Look for disconnected cables, damaged sensors, power issues",
        ),
        ProcedureStep(
            number=3,
            action="Wait for diagnosis completion and next steps from AIA",
            target="Voice Assistant",
            wait_condition="diagnosis complete",
        ),
        ProcedureStep(
            number=4,
            action="Receive corrective procedures from AIA",
            target="Voice Assistant",
            notes="AIA will provide specific repair procedures based on findings",
        ),
    ]
)

LTV_REPAIR_BUS_CONNECTOR = Procedure(
    name="LTV Bus Connector Repair",
    description="Reconnect loose bus connector (power systems restoration)",
    mission_phase="repair",
    steps=[
        ProcedureStep(
            number=1,
            action="Locate loose bus connector",
            target="EV",
            notes="Check power system connections near main LTV control board",
        ),
        ProcedureStep(
            number=2,
            action="Verify power systems are limited due to disconnection",
            target="EV",
            notes="Confirm reduced functionality before attempting repair",
        ),
        ProcedureStep(
            number=3,
            action="Reconnect the bus connector securely",
            target="EV",
            notes="Ensure full seating and locking tabs engaged",
        ),
        ProcedureStep(
            number=4,
            action="Wait for AIA to confirm power restoration",
            target="Voice Assistant",
            wait_condition="power systems nominal",
        ),
    ]
)

LTV_REPAIR_DUST_SENSOR = Procedure(
    name="LTV Dust Sensor Replacement",
    description="Replace damaged dust sensor (optional if time permits)",
    mission_phase="repair",
    steps=[
        ProcedureStep(
            number=1,
            action="Locate damaged dust sensor",
            target="EV",
            notes="Check navigation sensor array on forward boom",
        ),
        ProcedureStep(
            number=2,
            action="Remove damaged sensor and install replacement",
            target="EV",
            notes="Align connector before insertion; this can be deferred if low on time",
        ),
        ProcedureStep(
            number=3,
            action="Wait for AIA to verify sensor is operational",
            target="Voice Assistant",
            wait_condition="sensor operational and calibrated",
        ),
    ]
)

LTV_VERIFICATION = Procedure(
    name="LTV Final Verification",
    description="Conduct final system verification to ensure recovery is successful",
    mission_phase="repair",
    steps=[
        ProcedureStep(
            number=1,
            action="Command AIA to conduct final system diagnosis",
            target="Voice Assistant",
        ),
        ProcedureStep(
            number=2,
            action="Wait for AIA to verify rover is stable and recovery is successful",
            target="Voice Assistant",
            wait_condition="all systems nominal",
        ),
    ]
)

# Procedure database indexed by name
PROCEDURE_DATABASE: Dict[str, Procedure] = {
    "uia_egress": UIA_EGRESS_PROCEDURES,
    "egress": UIA_EGRESS_PROCEDURES,
    "eva egress": UIA_EGRESS_PROCEDURES,
    "ltv_erp": LTV_ERM_PROCEDURE,
    "ltv_exit_recovery_mode": LTV_ERM_PROCEDURE,
    "exit_recovery_mode": LTV_ERM_PROCEDURE,
    "erp": LTV_ERM_PROCEDURE,
    "ltv_diagnosis": LTV_DIAGNOSIS_PROCEDURE,
    "system_diagnosis": LTV_DIAGNOSIS_PROCEDURE,
    "diagnosis": LTV_DIAGNOSIS_PROCEDURE,
    "ltv_repair_bus_connector": LTV_REPAIR_BUS_CONNECTOR,
    "bus_connector": LTV_REPAIR_BUS_CONNECTOR,
    "connector_repair": LTV_REPAIR_BUS_CONNECTOR,
    "ltv_repair_dust_sensor": LTV_REPAIR_DUST_SENSOR,
    "dust_sensor": LTV_REPAIR_DUST_SENSOR,
    "sensor_replacement": LTV_REPAIR_DUST_SENSOR,
    "ltv_verification": LTV_VERIFICATION,
    "final_verification": LTV_VERIFICATION,
    "verification": LTV_VERIFICATION,
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
        "walk through", "walkthrough", "instruction", "instructions",
        "exit recovery", "erm", "erp", "diagnosis", "diagnose", "bus connector",
        "dust sensor", "sensor replacement", "verification", "verify"
    }
    return any(keyword in normalized for keyword in procedure_keywords)
