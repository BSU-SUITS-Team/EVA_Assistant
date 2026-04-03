# EVA Assistant
Local chatbot powered by Ollama. Fetches live telemetry from your HTTPS server and performs arithmetic calculations for mission-critical queries.

## Prerequisites
* Python 3.8+
* pip (Python package installer)
* Ollama (for LLM inference)

## Dependencies
* **Ollama**
  * Local LLM runtime for Mistral 7B model
* **LangChain**
  * Framework for LLM prompt engineering and chaining
* **Requests**
  * HTTP library for fetching telemetry from server

See [requirements.txt](requirements.txt) for full list.

## Architecture

The EVA Assistant uses a **direct data access** approach (no vector database):

1. **Background Polling** — Fetches telemetry from server every 1 second (matching frontend)
2. **Live Data** — Always passes current telemetry to LLM
3. **Arithmetic Only** — Mistral performs calculations on real values
4. **Thread-Safe** — Background thread + main thread coordinate via locks

For detailed data sync configuration, see [DATA_SYNC.md](DATA_SYNC.md).

## Usage

### Python Setup/Installation

This project runs through a venv virtual environment to keep dependencies isolated:

Linux/macOS:
```bash
./venv/bin/activate
pip install -r ./requirements.txt
```

Windows:
```bash
./venv/Scripts/activate
pip install -r ./requirements.txt
```

### Ollama Setup

Download [Ollama](https://ollama.com/) from their website and install.

Then pull the Mistral model (used for LLM inference):
```bash
ollama pull mistral
```

Start the Ollama server (before running the assistant):
```bash
ollama serve
```

This runs in the background on `localhost:11434` by default.

### Running the Assistant

```bash
cd src
python3 main.py
```

The assistant will:
1. Start background polling (fetches server data every 1 second)
2. Connect to Ollama for LLM inference
3. Accept questions and return arithmetic results

### Configuration

Set environment variables to customize behavior:

```bash
# Change server URL (defaults to http://192.168.0.11:14141)
export TELEMETRY_SERVER_BASE="http://your-server:port"

# Then run
python3 main.py
```

For more options, see [DATA_SYNC.md](DATA_SYNC.md).

## Core Components

1. **LLM Layer** ([main.py](src/main.py))
   - Uses Ollama with Mistral 7B model
   - LangChain ChatPromptTemplate for prompt engineering
   - Configured for arithmetic-only calculations with temperature=0.0

2. **Data Layer** ([telemetry.py](src/telemetry.py))
   - Fetches EVA.json, ROVER.json, LTV.json from `/data/` endpoint
   - Background daemon thread polls every 1 second
   - Thread-safe access to current telemetry data
   - Automatic retry on fetch failure

3. **Data Format**
   - Input: Nested JSON from server
   - Transform: Flatten to readable text format
   - Output: Direct to LLM (no indexing or ranking)

## Execution Flow

```
┌─ Background Thread ──────────────────────┐
│ Every 1 second:                          │
│ Fetch EVA.json, ROVER.json, LTV.json    │
│ Merge into _current_telemetry            │
└──────────────────────────────────────────┘
                ↓
          User Question
                ↓
      get_current_telemetry()
                ↓
     format_telemetry_for_llm()
                ↓
        LLM Arithmetic Chain
                ↓
         Return Answer
```

## Example Usage

```
Ask your question (q to quit): What is the primary oxygen storage for EVA1?

Telemetry data:
[TELEMETRY]
  telemetry.eva1.oxy_pri_storage: 85.2

Answer: The primary oxygen storage for EVA1 is 85.2%
```

## Troubleshooting

**"Failed to connect to Ollama"**
- Make sure Ollama is running: `ollama serve`

**"Failed to fetch telemetry"**
- Check server is running and accessible
- Verify `TELEMETRY_SERVER_BASE` is correct
- Test with: `curl http://192.168.0.11:14141/data/EVA.json`

**LLM returns "not provided"**
- Verify field exists in server telemetry
- Check exact field name (case-sensitive)
- Review debug logs for actual data fetched

## Future Enhancements

* Add vector database layer for semantic search (if needed)
* Implement UDP socket communication for commands
* Add conversation history persistence
* Optimize LLM prompts for specific mission contexts
* Add alert/anomaly detection thresholds
