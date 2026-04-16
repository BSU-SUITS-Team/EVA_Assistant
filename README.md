# EVA Assistant
Local chatbot powered by Ollama. Fetches live telemetry from HTTPS server and performs arithmetic calculations for mission-critical queries.

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
# Change server URL (defaults to http://localhost:11434)
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
- Test with: `curl http://localhost:11434/data/EVA.json`

**LLM returns "not provided"**
- Verify field exists in server telemetry
- Check exact field name (case-sensitive)
- Review debug logs for actual data fetched

## Future Enhancements

* Add schema validation in telemetry.py before anything reaches the model. Define required fields, types, units, and valid ranges, and reject or flag anything that does not match.

* Stop relying on flattened prose for reasoning in main.py. Keep the raw structured telemetry available, and pass the model a compact, explicit structure with field paths and units so it cannot easily mix values together.

* Move arithmetic out of the model. If the question is numeric, calculate it in Python and have the model only explain or format the result.

* Add a post-answer verifier. Check that every number in the response exists in the source telemetry and that the units and field names line up before printing the answer.

* Improve failure handling at startup and during polling in telemetry.py. Right now the app exits if initial fetch fails; that is brittle. It should either retry, fall back cleanly, or keep running in a degraded state.

* Keep the local model, but choose a stronger instruction-tuned one if possible. Mistral can work, but for strict structured answers, test Qwen2.5 Instruct or Llama 3.1 Instruct locally, then compare which one makes fewer field-misread errors at temperature 0.0.

* Add tests for the failure modes that matter most. Focus on missing fields, swapped labels, stale telemetry, malformed JSON, and unit mismatches in the files under tests.