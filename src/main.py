from langchain_ollama.llms import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from vector import retriever
import logging

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

model = OllamaLLM(model="mistral", temperature=0.0)
MAX_HISTORY_TURNS = 6

'''
Simplified template for arithmetic-only calculations on telemetry data.
Optimized for accuracy with temperature=0.0 for deterministic results.
'''
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

Calculation needed: {question}

Calculation:
"""
prompt = ChatPromptTemplate.from_template(template)
chain = prompt | model


def format_retrieved_context(documents, limit_to_top_n=3):
    """
    Format retrieved documents minimally for arithmetic calculations.
    Only passes the top N most relevant documents to reduce noise.
    """
    if not documents:
        return "No telemetry context found in vector database."

    # Only use top N documents to reduce context noise
    documents = documents[:limit_to_top_n]
    
    formatted = []
    for doc in documents:
        formatted.append(doc.page_content)
    
    if not formatted:
        return "Retrieved data but could not format it."
    
    result = "\n".join(formatted)
    return result


def normalize_question(question):
    """
    Normalize question to match telemetry field names.
    Expands queries with common synonyms before semantic search.
    """
    synonyms = {
        "oxygen": ["oxy", "o2", "o₂"],
        "battery": ["power", "charge"],
        "temperature": ["temp", "thermal"],
        "pressure": ["psi", "bar"],
        "tank": ["storage", "container"],
        "consumption": ["usage", "depletion", "burn"],
        "time remaining": ["duration", "eta", "how long"],
    }
    
    expanded = question.lower()
    for field, aliases in synonyms.items():
        for alias in aliases:
            if alias in expanded:
                expanded += f" {field}"
    return expanded


def format_chat_history(chat_history):
    if not chat_history:
        return "No prior conversation."

    # Only show last 2 turns for calculation context
    recent_turns = chat_history[-2:]
    return "\n".join(
        f"User: {turn['question']}\nAssistant: {turn['answer']}"
        for turn in recent_turns
    )


chat_history = []

# Allows user to ask questions until they type 'q' to quit
while True:
    print("\n" + "="*50)
    question = input("Ask your question (q to quit): ").strip()
    print()
    if question.lower() == "q":
        print("Exiting assistant. Goodbye!")
        break
    
    if not question:
        print("Please enter a question.")
        continue

    # Normalize question to improve retrieval accuracy
    normalized_question = normalize_question(question)
    telemetry_docs = retriever.invoke(normalized_question)
    telemetry_context = format_retrieved_context(telemetry_docs, limit_to_top_n=3)
    
    result = chain.invoke(
        {
            "telemetry": telemetry_context,
            "question": question,
        }
    )

    chat_history.append({"question": question, "answer": result})
    if len(chat_history) > MAX_HISTORY_TURNS:
        chat_history = chat_history[-MAX_HISTORY_TURNS:]

    print(f"\nAssistant: {result}")