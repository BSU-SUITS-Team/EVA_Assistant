"""
EVA Assistant - Main CLI Entry Point
Direct telemetry fetch + LLM arithmetic (no vector database)
Fetches telemetry every second in background
"""

import logging

from answer_formatter import _format_answer_with_llm, build_question_context
from procedure_handler import handle_procedure_request
from question_resolver import resolve_question
from telemetry import get_current_telemetry, start_polling

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_HISTORY_TURNS = 6

# Chat history
chat_history = []

# Main loop
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("EVA Assistant (Live Telemetry Mode)")
    print("=" * 60)

    # Start background polling
    print("\nInitializing telemetry polling...")
    if not start_polling():
        print("ERROR: Could not start telemetry polling. Exiting.")
        exit(1)

    print("Telemetry polling active (updates every 1 second)\n")

    # Question loop
    while True:
        print("=" * 60)
        question = input("Ask your question (q to quit): ").strip()
        print()

        if question.lower() == "q":
            print("Exiting assistant. Goodbye!")
            break

        if not question:
            print("Please enter a question.")
            continue

        try:
            # Check if this is a procedure request first
            procedure_response = handle_procedure_request(question)
            if procedure_response:
                print(f"Assistant: {procedure_response}\n")
                chat_history.append({"question": question, "answer": procedure_response})
                if len(chat_history) > MAX_HISTORY_TURNS:
                    chat_history = chat_history[-MAX_HISTORY_TURNS:]
                continue

            # Otherwise, treat as telemetry/data question
            telemetry_data = get_current_telemetry()
            if not telemetry_data:
                print("ERROR: No telemetry data available\n")
                continue

            telemetry_context = build_question_context(question, telemetry_data)
            if telemetry_context == "[]":
                print("Assistant: not provided\n")
                continue

            logger.info("Processing question: %s", question)
            result, matched_rows = resolve_question(question, telemetry_data)
            result_text = _format_answer_with_llm(result, question)

            chat_history.append({"question": question, "answer": result_text})
            if len(chat_history) > MAX_HISTORY_TURNS:
                chat_history = chat_history[-MAX_HISTORY_TURNS:]

            print(f"Assistant: {result_text}\n")

        except Exception as e:
            logger.error("Error processing question: %s", e)
            print(f"ERROR: {e}\n")
