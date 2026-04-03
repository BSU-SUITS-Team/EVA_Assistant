"""
EVA Assistant - Simplified version
Direct telemetry fetch + LLM arithmetic (no vector database)
Fetches telemetry every second in background
"""

from langchain_ollama.llms import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from telemetry import start_polling, get_current_telemetry, format_telemetry_for_llm
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize LLM
model = OllamaLLM(model="mistral", temperature=0.0)
MAX_HISTORY_TURNS = 6

# Prompt template for arithmetic-only calculations
template = """
You are an astronaut support system calculating telemetry values.

**TASK:** Perform ONLY basic arithmetic using the provided telemetry data.

**RULES:**
1. Extract ONLY numeric values that are explicitly provided
2. Show each calculation step clearly
3. If data is missing, return: "not provided"
4. Do NOT estimate, interpret, or use external knowledge
5. Return ONLY the final number or result

Telemetry data:
{telemetry}

Question: {question}

Answer:
"""

prompt = ChatPromptTemplate.from_template(template)
chain = prompt | model

# Chat history
chat_history = []

# Main loop
print("\n" + "="*60)
print("EVA Assistant (Live Telemetry Mode)")
print("="*60)

# Start background polling
print("\nInitializing telemetry polling...")
if not start_polling():
    print("ERROR: Could not start telemetry polling. Exiting.")
    exit(1)

print("✓ Telemetry polling active (updates every 1 second)\n")

# Question loop
while True:
    print("="*60)
    question = input("Ask your question (q to quit): ").strip()
    print()
    
    if question.lower() == "q":
        print("Exiting assistant. Goodbye!")
        break
    
    if not question:
        print("Please enter a question.")
        continue
    
    try:
        # Get latest telemetry data
        telemetry_data = get_current_telemetry()
        if not telemetry_data:
            print("ERROR: No telemetry data available\n")
            continue
        
        telemetry_text = format_telemetry_for_llm(telemetry_data)
        
        # Pass telemetry directly to LLM
        logger.info(f"Processing question: {question}")
        result = chain.invoke(
            {
                "telemetry": telemetry_text,
                "question": question,
            }
        )
        
        chat_history.append({"question": question, "answer": result})
        if len(chat_history) > MAX_HISTORY_TURNS:
            chat_history = chat_history[-MAX_HISTORY_TURNS:]
        
        print(f"Assistant: {result}\n")
        
    except Exception as e:
        logger.error(f"Error processing question: {e}")
        print(f"ERROR: {e}\n")