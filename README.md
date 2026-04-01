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
* **Vector Store:** Chroma w/ persistent storage at chroma-langchain_db (absolute path)
* **Retriever:** Dynamic k=5-10 semantic search (adapts to available documents)
* **Document Strategy:** Subsystem-based grouping for related field coherence

3. **Data Processing Pipeline**
* **Input:** JSON telemetry files from ./data directory
* **Transformation:** Groups related telemetry fields by subsystem (oxygen_system, power_system, co2_removal, cooling_system, biometrics, mission_time)
* **Indexing:** Creates two types of documents per EVA session:
  - **Full telemetry:** Complete dataset for "give me all data" queries
  - **Subsystem documents:** Grouped fields for system-specific queries and calculations
* **Storage:** Only new documents are added (deduplication by document ID)
* **Logging:** Tracks document loading, retrieval, and database health

## Execution Flow
User Question

↓

[Retriever] → Semantic search in vector DB → Most relevant subsystem/full telemetry documents

↓

[Formatter] → Organize retrieved documents, prioritize full telemetry for complete datasets

↓

[LLM Chain] → Generate response with complete subsystem context (enables calculations)

↓

[Memory] → Store Q&A pair (max 6 turns kept in history)

## Key Improvements
* **Better Calculations:** Subsystem grouping ensures all related data (e.g., oxygen storage + consumption rate) is retrieved together for accurate computations
* **Full Telemetry Support:** Complete EVA datasets available in a single document for comprehensive queries
* **Robust Paths:** Absolute path resolution prevents database lookup failures due to working directory changes
* **Enhanced Debugging:** Logging throughout pipeline tracks retrieval and document processing for troubleshooting
* **Dynamic Retrieval:** k parameter adapts to available documents, preventing under-retrieval

## Troubleshooting
* **Stale Data:** Delete `chroma-langchain_db/` folder and re-run `main.py` to rebuild the vector database with new subsystem structure
* **Missing Telemetry:** Check console logs for data loading errors; ensure `data/*.json` files are valid JSON
* **No Results:** Verify Ollama server is running and models (llama3.2, mxbai-embed-large) are installed

## Future Updates
* Persistent conversation history backend for multi-session context
* Prompt optimization with different designs and Ollama CLI parameters
* Web UI frontend for easier interaction
* Support for additional telemetry formats and real-time data streams
* Temperature and other LLM parameter tuning for calculation accuracy
