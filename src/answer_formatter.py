"""
Answer formatting: deterministic formatting and optional LLM formatting with guardrails.
Converts TelemetryAnswer to human-readable text, with optional LLM enhancement.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

# Optional LLM imports for natural language formatting
try:
    from langchain_ollama import OllamaLLM
    LLM_AVAILABLE = True
except ImportError:
    # Define as None when unavailable so it's always bound
    OllamaLLM = None  # type: ignore
    LLM_AVAILABLE = False

from question_resolver import TelemetryAnswer

logger = logging.getLogger(__name__)


def _format_numeric_value(value: Any) -> str:
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return format(value, "g")
    return str(value)


def _extract_numeric_from_text(text: str) -> Optional[float]:
    """Extract numeric value from formatted text (e.g., '47%' -> 47.0)."""
    match = re.search(r'-?\d+\.?\d*', text)
    if match:
        try:
            return float(match.group())
        except ValueError:
            return None
    return None


def _extract_numeric_value(value: Any) -> Optional[float]:
    """Extract numeric value from telemetry value."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace("%", "")
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _validate_numeric_guardrail(original_value: Any, llm_response: str) -> bool:
    """Check that LLM response preserves the numeric value (with tolerance for formatting)."""
    if original_value is None:
        return True  # No value to validate
    
    original_numeric = _extract_numeric_value(original_value)
    if original_numeric is None:
        return True  # Non-numeric, can't validate
    
    llm_numeric = _extract_numeric_from_text(llm_response)
    if llm_numeric is None:
        return False  # LLM response has no numeric value; suspicious
    
    # Allow 1% tolerance for floating-point differences
    tolerance = max(abs(original_numeric * 0.01), 0.1)
    return abs(original_numeric - llm_numeric) <= tolerance


def format_answer(answer: TelemetryAnswer) -> str:
    """Format a TelemetryAnswer into human-readable text."""
    if answer.value is None:
        return "not provided"

    if answer.kind == "time":
        from question_resolver import _format_duration
        duration_text = _format_duration(float(answer.value))
        if answer.entity != "UNKNOWN":
            return f"{answer.entity} {answer.label} is {duration_text}."
        return f"{answer.label.capitalize()} is {duration_text}."

    value_text = _format_numeric_value(answer.value)
    if answer.kind == "percent" and not value_text.endswith("%"):
        value_text = f"{value_text}%"
    elif answer.unit and answer.unit != "unknown" and not value_text.endswith(answer.unit):
        value_text = f"{value_text} {answer.unit}" if answer.unit not in {"%", "bpm", "psi"} else value_text

    label_text = answer.label.strip().lower()
    if label_text == "battery":
        label_text = "battery level"
    if label_text and answer.entity != "UNKNOWN":
        return f"{answer.entity} {label_text} is {value_text}."
    if label_text:
        return f"{label_text.capitalize()} is {value_text}."

    if answer.entity != "UNKNOWN":
        return f"{answer.entity} value is {value_text}."
    return f"Value is {value_text}."


def _format_answer_with_llm(answer: TelemetryAnswer, question: str) -> str:
    """
    Format answer using LLM if available, with guardrails to preserve numeric value.
    Falls back to deterministic formatting if LLM unavailable or guardrail fails.
    """
    if not LLM_AVAILABLE:
        # LLM not installed; use default formatting
        return format_answer(answer)
    
    if answer.value is None:
        return format_answer(answer)  # Can't format None values
    
    # Get the deterministic baseline answer
    baseline_answer = format_answer(answer)
    
    try:
        # Initialize Ollama LLM (uses llama2 by default, adjust model as needed)
        # Type guard: OllamaLLM is guaranteed not None due to LLM_AVAILABLE check above
        assert OllamaLLM is not None, "OllamaLLM should not be None when LLM_AVAILABLE is True"
        
        llm = OllamaLLM(
            model="llama2",
            temperature=0.3,  # Low temperature for consistency
        )
        
        # Build context for the LLM
        value_text = _format_numeric_value(answer.value)
        if answer.kind == "percent" and not value_text.endswith("%"):
            value_text = f"{value_text}%"
        elif answer.unit and answer.unit != "unknown":
            if answer.unit not in {"%", "bpm", "psi"}:
                value_text = f"{value_text} {answer.unit}"
        
        prompt = f"""You are a concise voice assistant for a lunar spacesuit. Rewrite the following answer in natural, clear language for the astronaut. 
Keep it brief (1-2 sentences). DO NOT CHANGE the numeric values.

Original answer: {baseline_answer}
Question asked: {question}
Key fact: {answer.label} for {answer.entity} is {value_text}.

Rewrite (natural, concise, numeric values preserved):"""
        
        llm_response = llm.invoke(prompt).strip()
        
        # Apply guardrail: verify numeric value is preserved
        if _validate_numeric_guardrail(answer.value, llm_response):
            logger.info("LLM formatter accepted response (guardrail passed)")
            return llm_response
        else:
            logger.warning("LLM response failed numeric guardrail; falling back to deterministic format")
            return baseline_answer
    
    except Exception as e:
        logger.warning(f"LLM formatting failed ({e}); falling back to deterministic format")
        return baseline_answer


def build_question_context(question: str, telemetry_data: Dict[str, Any]) -> str:
    """Build structured telemetry context for question answering."""
    from question_resolver import _flatten_telemetry, select_relevant_rows
    
    rows = _flatten_telemetry(telemetry_data)
    relevant_rows = select_relevant_rows(question, rows)

    logger.info(
        "Prepared %s structured telemetry fields for LLM (%s relevant rows)",
        len(rows),
        len(relevant_rows),
    )

    return json.dumps(relevant_rows, indent=2, sort_keys=True)
