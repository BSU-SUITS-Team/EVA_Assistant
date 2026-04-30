"""
Procedure guidance handler: manages step-by-step procedure walkthroughs.
Provides human-readable guidance with confirmation flow.
"""

import logging
import re
from typing import Optional, Tuple

from procedures import Procedure, is_procedure_request, get_procedure, list_available_procedures
from procedure_store import get_error_metadata, list_active_errors

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
    # Try to extract procedure name from question
    question_lower = question.lower()

    # Direct 4-digit LTV error code lookup from TSS payload.
    # Handle code-only or malformed prompts before any keyword gating.
    code_match = re.search(r"\b(\d{4})\b", question_lower)
    if code_match:
        error_id = code_match.group(1)
        metadata = get_error_metadata(error_id)
        proc = get_procedure(error_id)
        if proc:
            guide = ProcedureGuide(proc)
            heading = f"Error {metadata.get('code', error_id)}" if metadata else f"Error {error_id}"
            description = metadata.get("description", proc.name) if metadata else proc.name
            status = "ACTIVE" if metadata and metadata.get("needs_resolved") else "REPORTED"
            return f"{heading} - {description}\nStatus: {status}\n\n{guide.format_all_steps()}"

        active_errors = list_active_errors()
        available_codes = []
        for entry in active_errors:
            available_codes.append(str(entry.get("code", "unknown")))

        if active_errors:
            return (
                f"Error {error_id} is not present in the current runtime LTV_ERRORS.json.\n"
                f"Active error codes: {', '.join(available_codes)}\n\n"
                f"Ask about one of the active codes, or ask 'What errors do I have?'"
            )

        return f"Error {error_id} is not present in the current runtime LTV_ERRORS.json."

    if not is_procedure_request(question):
        return None

    # Active error summary questions should return the unresolved error list.
    if any(phrase in question_lower for phrase in (
        "what errors do i have",
        "do i have any active errors",
        "active errors",
        "active error codes",
        "what are my active error codes",
        "what are my active errors",
        "current error codes",
        "which errors",
        "what errors are active",
    )):
        active_errors = list_active_errors()
        if not active_errors:
            return "No active errors are currently reported in LTV_ERROS.json."

        lines = [f"Active errors ({len(active_errors)}):"]
        for entry in active_errors:
            code = entry.get("code", "unknown")
            description = entry.get("description", "")
            lines.append(f"- {code}: {description}")
        lines.append("")
        lines.append("Ask for a specific code, for example: 'What is 4800?' or 'Tell me about error 4509.'")
        return "\n".join(lines)

    # Direct matches for egress (UIA remains local; LTV resolves at runtime)
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
    available = list_available_procedures()
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
