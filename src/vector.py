from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
import json
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent / "data"
DB_LOCATION = "./chroma-langchain_db"


def _flatten_json(obj, parent_key=""):
    """Yield flattened key/value pairs from nested JSON objects."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            next_key = f"{parent_key}.{key}" if parent_key else key
            yield from _flatten_json(value, next_key)
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            next_key = f"{parent_key}[{index}]"
            yield from _flatten_json(value, next_key)
    else:
        yield parent_key, obj


def _load_documents_from_json(data_dir):
    documents = []
    ids = []

    json_files = sorted(data_dir.glob("*.json"))
    for file_path in json_files:
        with file_path.open("r", encoding="utf-8") as file:
            payload = json.load(file)

        flattened = list(_flatten_json(payload))
        for idx, (field, value) in enumerate(flattened):
            doc_id = f"{file_path.stem}:{idx}"
            document = Document(
                page_content=(
                    f"source_file: {file_path.name}\n"
                    f"field: {field}\n"
                    f"value: {value}"
                ),
                metadata={"source_file": file_path.name, "field": field},
                id=doc_id,
            )
            documents.append(document)
            ids.append(doc_id)

    return documents, ids


embeddings = OllamaEmbeddings(model="mxbai-embed-large")
documents, ids = _load_documents_from_json(DATA_DIR)

vector_store = Chroma(
    collection_name="telemetry",
    persist_directory=DB_LOCATION,
    embedding_function=embeddings,
)

existing = vector_store.get(include=[])
existing_ids = set(existing.get("ids", []))

new_documents = []
new_ids = []
for document, doc_id in zip(documents, ids):
    if doc_id not in existing_ids:
        new_documents.append(document)
        new_ids.append(doc_id)

if new_documents:
    vector_store.add_documents(documents=new_documents, ids=new_ids)

retriever = vector_store.as_retriever(
    search_kwargs={"k": 5}
)