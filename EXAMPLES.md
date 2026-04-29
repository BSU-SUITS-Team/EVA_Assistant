# EVA Assistant Usage Examples

This document provides practical examples for common queries and use cases.

## Telemetry Queries

### Individual Field Lookup

**Question:** What is EVA1's primary oxygen storage?
```
Assistant: EVA1 primary o2 storage is 94.2001%.
```

**Question:** What is EVA2's primary battery level?
```
Assistant: EVA2 primary battery level is 100%.
```

**Question:** What is the oxygen pressure in EVA1's primary tank?
```
Assistant: EVA1 primary o2 pressure is 3500 psi.
```

**Question:** What's the coolant temperature?
```
Assistant: Tank 1 coolant temperature is 45°F.
```

### Multi-suit Queries (Sum/Average)

**Question:** What is the total oxygen storage across both EVA suits?
```
Assistant: Total EVA oxygen storage is 197.2%.
```

**Question:** What's the average battery level across EVA1 and EVA2?
```
Assistant: Average EVA battery level is 96.1%.
```

**Question:** Sum up all CO2 cartridge levels
```
Assistant: Total EVA CO2 cartridge level is 185.5%.
```

### Time-to-Threshold Calculations

**Question:** How long until EVA1's primary oxygen depletes?
```
Assistant: EVA1 primary O2 depletes in 39 minutes.
```
*Calculated from: current psi ÷ consumption rate*

**Question:** When will EVA1's battery reach 50%?
```
Assistant: EVA1 battery reaches 50% in approximately 4 hours.
```

### Equipment Status Checks

**Question:** What is the LTV battery status?
```
Assistant: LTV battery is 87.5%.
```

**Question:** What's the rover CO2 level?
```
Assistant: ROVER primary CO2 level is 42%.
```

**Question:** How's the primary fan functioning?
```
Assistant: EVA1 primary fan is operating normally (100% capacity).
```

---

## Procedure Guidance

### EVA Egress Preparation

**Question:** What is the EVA egress procedure?
```
============================================================
UIA EGRESS - EVA egress preparation: Connect UIA, depressurize, prep O2 tanks, final checks
============================================================
Progress: Step 1/26

→ Step 1: Verify umbilical connection from UIA to DCU (UIA and DCU)
→ Step 2: EMU PWR – ON (UIA)
→ Step 3: BATT – UMB (DCU)
...
(26 total steps with progress tracking)
```

**Question:** Walk me through the UIA egress steps
```
(Same as above - returns full procedure with step-by-step guidance)
```

### LTV Emergency Recovery

**Question:** How do I perform exit recovery mode?
```
============================================================
LTV EXIT RECOVERY MODE - Exit Recovery Mode (ERM) to restore LTV to operational state
============================================================
Progress: Step 1/4

→ Step 1: Ensure all occupants properly secured within LTV
  Target: LTV
→ Step 2: Activate backup power systems
  Target: LTV Power Bus
...
(4 total steps for recovery)
```

**Question:** What are the ERM steps?
```
(Same as above - returns LTV Exit Recovery Mode procedure)
```

### LTV Diagnostics and Repair

**Question:** What is the LTV diagnostic procedure?
```
============================================================
LTV SYSTEM DIAGNOSIS - Perform system diagnosis to identify LTV malfunctions
============================================================
Progress: Step 1/4

→ Step 1: Conduct visual inspection of exterior for visible damage
  Target: LTV Exterior
→ Step 2: Check all panel lights and indicators
  Target: LTV Control Panel
...
(4 total steps for diagnosis)
```

**Question:** How do I repair the bus connector?
```
============================================================
LTV BUS CONNECTOR REPAIR - Reconnect loose bus connector (power systems restoration)
============================================================
Progress: Step 1/4

→ Step 1: Locate the power bus connector on the drive unit
  Target: LTV Drive Unit
→ Step 2: Inspect connector for damage or debris
  Target: Power Connector
...
(4 total steps for connector repair)
```

**Question:** Dust sensor replacement procedure
```
============================================================
LTV DUST SENSOR REPLACEMENT - Replace damaged dust sensor (optional if time permits)
============================================================
Progress: Step 1/3

→ Step 1: Locate dust sensor on the LTV navigation system
  Target: LTV Navigation Module
→ Step 2: Carefully remove damaged sensor
  Target: Dust Sensor Assembly
...
(3 total steps for sensor replacement)
```

### LTV Final Verification

**Question:** What is the final verification?
```
============================================================
LTV FINAL VERIFICATION - Conduct final system verification to ensure recovery is successful
============================================================
Progress: Step 1/2

→ Step 1: Test all primary systems (power, communications, navigation)
  Target: LTV Control Systems
→ Step 2: Confirm propulsion and steering response
  Target: LTV Drive Systems
```

### Repair Help Menu

**Question:** Can you help me with LTV repairs?
```
Available repair procedures:
  • Exit Recovery Mode (ERM) - Restore LTV to operational state
  • System Diagnosis - Identify malfunctions
  • Bus Connector Repair - Restore power systems
  • Dust Sensor Replacement - Fix navigation sensors
  • Final Verification - Confirm successful recovery

Ask for a specific procedure (e.g., "How do I perform system diagnosis?")
```

---

## Complex Query Patterns

### Multi-part Questions

**Question:** What is EVA1's O2 storage and battery level?
```
Assistant: EVA1 primary o2 storage is 94.2001%. EVA1 primary battery level is 96.1998%.
```

### Comparative Queries

**Question:** Which EVA suit has more oxygen?
```
Assistant: EVA1 primary o2 storage is 94.2001%, EVA2 primary o2 storage is 100%. 
EVA2 has higher oxygen storage.
```

### Arithmetic Operations

**Question:** What's the difference between EVA1 and EVA2 battery levels?
```
Assistant: EVA1 battery is 96.1998%, EVA2 battery is 100%. Difference is 3.8002%.
```

---

## Tips for Better Questions

### Clear, Direct Questions
❌ "Tell me about oxygen"  
✅ "What is EVA1's primary oxygen storage?"

❌ "Procedures?"  
✅ "What is the egress procedure?"

### Specific Entity Names
❌ "What's the battery?"  
✅ "What is EVA1's primary battery level?"

### Use Expected Keywords
For procedures, include: "procedure", "steps", "guide", "how to", "walk through"  
Examples:
- "EVA egress procedure"
- "How do I perform system diagnosis?"
- "LTV repair steps"

---

## Troubleshooting Query Issues

| Issue | Solution |
|-------|----------|
| "Not sure what you're asking" | Be more specific with suit/component names (EVA1, EVA2, LTV, ROVER) |
| Procedure not found | Include keywords like "procedure", "steps", or "how to" |
| Unexpected telemetry value | Try asking about a specific part of the equipment (e.g., "primary" vs "secondary") |
| Arithmetic result seems wrong | Note: Depletion time is calculated from pressure consumption rates, not percentages |

---

## Sample Session

```
Ask your question (q to quit): What is EVA1's primary oxygen storage?
Assistant: EVA1 primary o2 storage is 94.2001%.

Ask your question (q to quit): How long until it depletes?
Assistant: EVA1 primary O2 depletes in 39 minutes.

Ask your question (q to quit): What is the EVA egress procedure?
Assistant: [26-step procedure with progress tracking]

Ask your question (q to quit): q
Exiting assistant. Goodbye!
```
