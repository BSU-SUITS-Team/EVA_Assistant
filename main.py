from langchain_ollama.llms import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate

model = OllamaLLM(model="llama3.2")

# Tempate to feed into the model to allow it to create a curated response
template = """
You are supporting an astronaut during a lunar mission.

Here are the current vitals: {vitals}

Here is the question to answer: {question} 
"""
prompt = ChatPromptTemplate.from_template(template)
chain = prompt | model

# Allows user to ask questions until they prompt they are done
while True:
    print("\n\n-------------------------")
    question = input("Ask your question (q to quit): ")
    print("\n\n")
    if question == "q":
        break

    result = chain.invoke({"vitals": [], "question": question})
    print(result)