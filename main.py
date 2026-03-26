from langchain_ollama.llms import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from vector import retriever


model = OllamaLLM(model="llama3.2")

'''
Tempate to feed into the model to allow it to create a curated response

Currently prompting the model that it is supporting an astronaut during a lunar mission,
then feeding it the mission data and the question from the user.
'''
template = """
You are supporting an astronaut during a lunar mission. Responses are concise and only include
information relevant to the question asked.

Here are the current telemetry readings: {telemetry}

Here is the question to answer: {question} 
"""
prompt = ChatPromptTemplate.from_template(template)
chain = prompt | model


def format_retrieved_context(documents):
    if not documents:
        return "No telemetry context found in vector database."

    chunks = []
    for idx, doc in enumerate(documents, start=1):
        source_file = doc.metadata.get("source_file", "unknown")
        field = doc.metadata.get("field", "unknown")
        chunks.append(
            f"[{idx}] source_file={source_file} field={field}\n{doc.page_content}"
        )

    return "\n\n".join(chunks)

# Allows user to ask questions until they prompt they are done
while True:
    print("\n\n-------------------------")
    question = input("Ask your question (q to quit): ")
    print("\n\n")
    if question == "q":
        break

    telemetry_docs = retriever.invoke(question)
    telemetry_context = format_retrieved_context(telemetry_docs)
    result = chain.invoke({"telemetry": telemetry_context, "question": question})
    print(result)