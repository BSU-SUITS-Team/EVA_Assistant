from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
import os
import pandas as pd

# Need to be able to load in the JSON files with the telemetry data
df = pd.read_json("data/EVA.json")
embeddings = OllamaEmbeddings(model="mxbai-embed-large")

db_location = "./chroma-langchain_db"
add_documents = not os.path.exists("db_location")

if add_documents:
    documents = []
    ids = []

    for i, row in df.iterrows(): 
        document = Document(
            # TODO: figure out best way to structure database from JSON files
            page_content=row["Telemetry"] + ["eva"], 
            metadata={"telem_value": row["Telemtry Value"]},
            id=str(i)
        )
        ids.append(str(i))
        documents.append(document)

vector_store = Chroma(
    collection_name="telemetry",
    persist_directory=db_location,
    embedding_function=embeddings
)

if add_documents:
    vector_store.add_documents(documents=documents, ids=ids)

retriever = vector_store.as_retriever(
    search_kwargs={"k": 5}
)