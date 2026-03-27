# EVA Assistant
Local chatbot powered by Ollama. Implements a **Retrieval-Augmented Generation (RAG)** pipeline for mission-critical telemetry quireies.

## Prerequisites
* Python 3.8+
* pip (Python package installer)

## Dependencies
* Ollama
  * Stored locally on machine to run chatbot
* LangChain
  * Open-source framework with pre-built agent architecture and integrations
* Chroma
  * Vector store database
* Pandas
  * Library to read in files

## Usage

This project runs through a venv virtual environment in order to keep dependencies from interfering with other local projects.

### Python Setup/Installation
In the command terminal, you will need to load into the virtual environment first, before installing packages. To do this:

Linux/MAC:
```console
$ ./venv/bin/activate
$ pip install -r ./requirements.txt
```

Windows:
```console
$ ./venv/Scripts/activate
$ pip install -r ./requirements.txt
```
After running this, the required dependencies will be installed into the virtual environment to use.

### Ollama Setup
Next, to be able to locally run a model, you will need to download [Ollama](https://ollama.com/) from their website. 
This EVA assitant uses the llama3.2 model, as well as an embedding model mxbai-embed-large. We will download these from the console using the ollama command.

```console
$ ollama pull llama3.2
pulling manifest
...
success
$ ollama pull mxbai-embed-large
pulling manifest
...
success
```
### Starting Chat (currently in terminal)
To run the chat in the terminal:

Linx/MAC:
```console
$ cd ./src
$ python3 main.py
```
Windows:
```console
$ cd src
$ python main.py
```

## Core Components
1. **LLM Layer (main.py)**
* Uses Ollama with llama3.2 model
* Structured using LangChain's ChatPromptTemplate
* Role-based prompt that frames responses w/ astronaut support context

2. **Vector Database Layer (vector.py)**
* **Embedding Model:** mxbai-embed-large (Ollama embeddings)
* **Vector Store:** Chroma w/ persistent storage at chroma-langchain_db
* **Retriever:** k=5 semantic search (returns 5 most relevant documents)

3. **Data Processing Pipeline**
* **Input:** JSON telemetry files from ./data directory
* **Transformation:** Flattens nested JSON structures into individual field-value pairs
* **Indexing:** Each flattened field becomes a document with metadata (source file, field name)
* **Storage:** Only new documents are added (deduplication by document ID)

## Execution Flow
User Question

 ↓

[Retriever] → Semantic search in vector DB → Top 5 relevant telemetry fields

↓

[Formatter] → Format retrieved context + chat history

↓

[LLM Chain] → Generate concise response with context

↓

[Memory] → Store Q&A pair (max 6 turns kept)

## Needed Information/Discussion Topics
* Understanding the way the chatbot can reference mission information to create the proper output

## Future Updates
* Create backend functionality to store and use conversation history for more in-context responses.
* Optimize model reponse behavior with different prompt designs and Ollama CLI parameters.
* Create a more solidified environment for the chatbot.
