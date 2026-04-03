from langchain_ollama.llms import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from vector import retriever
import logging

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

model = OllamaLLM(model="mistral")
MAX_HISTORY_TURNS = 6

'''
Template to feed into the model to allow it to create a curated response.

Currently prompting the model that it is supporting an astronaut during a lunar mission,
then feeding it the mission data and the question from the user.

The template emphasizes:
- Using provided data for calculations
- Structured formatting of responses
- Clear reasoning for complex questions
'''
template = """
You are an astronaut support system. You have access to telemetry data.

**RULES:**
- Return ONLY values from the telemetry data below
- Do NOT make up or estimate values  
- If a value is not provided, say exactly: "not provided"
- For calculations, show all work using only provided numbers

Telemetry data:
{telemetry}

Previous conversation:
{chat_history}

Question: {question}

Response (use only data shown above):
"""
prompt = ChatPromptTemplate.from_template(template)
chain = prompt | model


def format_retrieved_context(documents):
    """
    Format retrieved documents for better LLM comprehension.
    Groups documents by type to maintain data relationships.
    """
    if not documents:
        return "No telemetry context found in vector database."

    # Group documents by type for better structure
    full_telemetry = []
    subsystems = {}
    
    for doc in documents:
        doc_type = doc.metadata.get("type", "unknown")
        
        if doc_type == "full_telemetry":
            full_telemetry.append(doc.page_content)
        elif doc_type == "subsystem":
            subsystem = doc.metadata.get("subsystem", "unknown")
            if subsystem not in subsystems:
                subsystems[subsystem] = []
            subsystems[subsystem].append(doc.page_content)
    
    # Build formatted output: prioritize full telemetry, then subsystems
    formatted = []
    
    if full_telemetry:
        formatted.extend(full_telemetry)
    
    for subsystem, contents in subsystems.items():
        formatted.extend(contents)
    
    if not formatted:
        return "Retrieved data but could not format it."
    
    result = "\n".join(formatted)
    return result


def format_chat_history(chat_history):
    if not chat_history:
        return "No prior conversation."

    return "\n".join(
        f"User: {turn['question']}\nAssistant: {turn['answer']}"
        for turn in chat_history
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

    telemetry_docs = retriever.invoke(question)
    telemetry_context = format_retrieved_context(telemetry_docs)
    history_context = format_chat_history(chat_history)
    
    result = chain.invoke(
        {
            "chat_history": history_context,
            "telemetry": telemetry_context,
            "question": question,
        }
    )

    chat_history.append({"question": question, "answer": result})
    if len(chat_history) > MAX_HISTORY_TURNS:
        chat_history = chat_history[-MAX_HISTORY_TURNS:]

    print(f"\nAssistant: {result}")