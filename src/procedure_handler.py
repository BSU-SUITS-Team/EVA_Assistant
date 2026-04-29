"""
Procedure guidance handler: manages step-by-step procedure walkthroughs.
Provides human-readable guidance with confirmation flow.
"""

import logging
from typing import Optional, Tuple

from procedures import Procedure, get_procedure, is_procedure_request

logger = logging.getLogger(__name__)


class ProcedureGuide:
    """Manages state and guidance for a procedure walkthrough."""
    
    def __init__(self, procedure: Procedure):
        self.procedure = procedure
        self.current_step_index = 0
        self.completed = False
    
    def get_current_step(self):
        """Get the current step or None if procedure is complete."""
        if self.current_step_index >= len(self.procedure.steps):
            self.completed = True
            return None
        return self.procedure.steps[self.current_step_index]
    
    def get_progress(self) -> Tuple[int, int]:
        """Get (current_step_number, total_steps)."""
        return (self.current_step_index + 1, len(self.procedure.steps))
    
    def advance_step(self) -> Optional[str]:
        """Move to next step. Return formatted guidance or None if complete."""
        if self.get_current_step() is None:
            return "Procedure complete!"
        
        self.current_step_index += 1
        return self.format_current_guidance()
    
    def format_current_guidance(self) -> str:
        """Format the current step as human-readable guidance."""
        step = self.get_current_step()
        if step is None:
            return "EVA Egress complete. Proceed to airlock."
        
        progress_num, total = self.get_progress()
        
        # Build step guidance
        lines = [
            f"\n{'='*60}",
            f"Step {progress_num}/{total}",
            f"{'='*60}",
            f"\nAction: {step.action}",
            f"Location: {step.target}",
        ]
        
        if step.wait_condition:
            lines.append(f"Wait for: {step.wait_condition}")
        
        if step.notes:
            lines.append(f"Note: {step.notes}")
        
        lines.append(f"\nConfirm step completion (Y/n): ")
        
        return "\n".join(lines)
    
    def format_all_steps(self) -> str:
        """Format all steps as a complete checklist."""
        current_idx = self.current_step_index
        
        lines = [
            f"\n{'='*60}",
            f"{self.procedure.name.upper()} - {self.procedure.description}",
            f"{'='*60}",
            f"Progress: Step {current_idx + 1}/{len(self.procedure.steps)}\n",
        ]
        
        for i, step in enumerate(self.procedure.steps):
            marker = "✓" if i < current_idx else "→" if i == current_idx else " "
            lines.append(f"{marker} Step {step.number}: {step.action} ({step.target})")
            if step.wait_condition:
                lines.append(f"     Wait: {step.wait_condition}")
        
        return "\n".join(lines)


def handle_procedure_request(question: str) -> Optional[str]:
    """
    Process a procedure request and return formatted guidance.
    Returns None if not a procedure request or procedure not found.
    """
    if not is_procedure_request(question):
        return None
    
    # Try to extract procedure name from question
    question_lower = question.lower()
    
    # Direct matches for egress
    if "egress" in question_lower:
        proc = get_procedure("egress")
        if proc:
            guide = ProcedureGuide(proc)
            return guide.format_all_steps()
    
    # LTV Exit Recovery Mode
    if "exit recovery" in question_lower or "erp" in question_lower or "erm" in question_lower:
        proc = get_procedure("exit_recovery_mode")
        if proc:
            guide = ProcedureGuide(proc)
            return guide.format_all_steps()
    
    # LTV System Diagnosis
    if "diagnosis" in question_lower or "diagnose" in question_lower:
        proc = get_procedure("system_diagnosis")
        if proc:
            guide = ProcedureGuide(proc)
            return guide.format_all_steps()
    
    # LTV Bus Connector Repair
    if "bus connector" in question_lower or "connector" in question_lower:
        proc = get_procedure("bus_connector")
        if proc:
            guide = ProcedureGuide(proc)
            return guide.format_all_steps()
    
    # LTV Dust Sensor Replacement
    if "dust sensor" in question_lower or "sensor replacement" in question_lower:
        proc = get_procedure("dust_sensor")
        if proc:
            guide = ProcedureGuide(proc)
            return guide.format_all_steps()
    
    # LTV Final Verification
    if "final verification" in question_lower or "verification" in question_lower:
        proc = get_procedure("verification")
        if proc:
            guide = ProcedureGuide(proc)
            return guide.format_all_steps()
    
    # Generic repair help
    if "repair" in question_lower:
        return f"""
Available repair procedures:
  • Exit Recovery Mode (ERM) - Restore LTV to operational state
  • System Diagnosis - Identify malfunctions
  • Bus Connector Repair - Restore power systems
  • Dust Sensor Replacement - Fix navigation sensors
  • Final Verification - Confirm successful recovery

Ask for a specific procedure (e.g., "How do I perform system diagnosis?")"""
    
    # Default fallback
    logger.warning(f"Procedure request not recognized: {question}")
    available = ["UIA Egress", "Exit Recovery Mode", "System Diagnosis", "Bus Connector", "Dust Sensor", "Final Verification"]
    return f"I can help with procedures. Available: {', '.join(available)}"


def format_procedure_start(procedure: Procedure) -> str:
    """Format initial guidance to start a procedure."""
    guide = ProcedureGuide(procedure)
    return f"""
{'='*60}
{procedure.name.upper()}
{'='*60}
{procedure.description}

Total steps: {len(procedure.steps)}

Starting procedure...
{guide.format_current_guidance()}"""
