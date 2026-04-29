# EVA Assistant
Local telemetry assistant that fetches live data from an HTTP server and performs field lookup and arithmetic in Python.

## Prerequisites
* Python 3.8+
* pip (Python package installer)
* Requests library installed from `requirements.txt`

## Dependencies
* **Requests**
  * HTTP library for fetching telemetry from the server
* **LangChain-Core** (optional)
  * For LLM-based answer formatting
* **LangChain-Ollama** (optional)
  * Integration with Ollama for local LLM inference
* **Ollama** (optional, requires setup)
  * Local LLM server for natural language generation

See [requirements.txt](requirements.txt) for the full list.

## Architecture

The EVA Assistant uses a direct data access approach with code-verified answers and optional LLM formatting:

1. Background Polling - Fetches telemetry from the server every second
2. Live Data - Keeps the latest server snapshot in memory for each source file
3. Code-Based Arithmetic - `main.py` resolves fields and computes numeric answers in Python
4. **Numeric Verification** - All values are locked as typed answers before LLM access
5. **LLM Natural Language (Optional)** - LLM formatter rewrites verified answers into natural language
6. **Guardrails** - Validates that LLM preserves numeric values; falls back to deterministic format if not
7. Thread-Safe - Background thread and main thread coordinate via locks

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

### Running the Assistant

```bash
cd src
python3 main.py
```

The assistant will:
1. Start background polling and fetch server data every 1 second
2. Resolve telemetry values and arithmetic in Python
3. (Optional) Use LLM to rewrite answers in natural language if Ollama is available
4. Format and return the final response

### Optional: Ollama Setup for LLM Natural Language Formatting

To enable natural language formatting via Ollama:

1. Install Ollama: https://ollama.ai/
2. Start the Ollama server:
   ```bash
   ollama serve
   ```
3. Pull a model (e.g., llama2):
   ```bash
   ollama pull llama2
   ```
4. Install LLM dependencies:
   ```bash
   pip install langchain-core langchain-ollama
   ```

The assistant will automatically use LLM formatting if available. If Ollama is not running or dependencies are missing, the assistant falls back to deterministic formatting with a guardrail check to ensure numeric values are preserved.

### Configuration

Set environment variables to customize behavior:

```bash
# Change telemetry server URL (defaults to http://172.17.0.1:14141)
export TELEMETRY_SERVER_BASE="http://your-server:port"

# Then run
python3 main.py
```

For more options, see [DATA_SYNC.md](DATA_SYNC.md).

## Core Components

1. **Answer Resolution** ([main.py](src/main.py))
   - Resolves telemetry values and arithmetic directly in Python
   - Applies explicit field routing for oxygen pressure, storage, consumption, and CO2 queries
   - Formats the final response deterministically in code

2. **Data Layer** ([telemetry.py](src/telemetry.py))
   - Fetches EVA.json, ROVER.json, and LTV.json from the `/data/` endpoint
   - Keeps each source file as a separate snapshot
   - Runs a background daemon thread that polls every second
   - Provides thread-safe access to current telemetry data
   - Retries on fetch failure

3. **Data Format**
   - Input: Nested JSON from the server
   - Transform: Flatten to structured rows with field paths, labels, and units
   - Output: Deterministic code path for value lookup, depletion estimates, and arithmetic

## Execution Flow

```
┌─ Background Thread 
│ Every 1 second:                                            
│ Fetch EVA.json, ROVER.json, LTV.json     
│ Store each file as a separate snapshot          

                ↓
          User Question
                ↓
      get_current_telemetry()
                ↓
     resolve_question() / arithmetic in code
                ↓
      TelemetryAnswer (verified, typed)
                ↓
    Optional: LLM rewrite with guardrails
     (preserves numeric values, falls back
      to deterministic if unavailable or fails)
                ↓
         Return Answer
```

## Example Usage

```
Ask your question (q to quit): What is EVA1's primary o2 storage percentage?

Answer: 96.45924377441406%
```

## Troubleshooting

**"Failed to fetch telemetry"**
- Check the telemetry server is running and accessible
- Verify `TELEMETRY_SERVER_BASE` is correct
- Test with: `curl http://172.17.0.1:14141/data/EVA.json`

**Assistant returns "not provided"**
- Verify the telemetry field exists in the server snapshot
- Check the question wording and the field alias used in `main.py`
- Review debug logs for the relevant row count

**Assistant returns the wrong oxygen field**
- Ask for `primary o2 pressure`, `primary o2 storage`, or `primary o2 consumption` explicitly
- Remember that pressure, storage, and consumption are routed separately
- If needed, add a new alias in the `_field_aliases()` table in [src/main.py](src/main.py)

**LLM formatter is not being used (returns deterministic format)**
- Verify Ollama is running: `curl http://localhost:11434/api/status`
- Confirm LangChain dependencies are installed: `pip install langchain-core langchain-ollama`
- Check logs for guardrail failures (LLM preserved numeric values incorrectly)
- Ensure the model is available: `ollama list`

**LLM responses seem hallucinated or numeric values are wrong**
- The guardrail check should catch this and fall back to deterministic formatting
- If this is still happening, check the LLM temperature setting (should be ~0.3 for consistency)
- Try a different model: `ollama pull mistral` and update the model name in `main.py`

## Future Enhancements

- [x] Add LLM formatter with safe guardrails to preserve numeric values from code verification
- [ ] Add UIA egress procedure guidance system (hardcoded, mission-critical)
- [ ] Add LTV diagnosis and repair procedure guidance with voice walkthrough
- [ ] Add predictive maximum range calculation based on consumable rates (O₂, coolant)
- [ ] Add caution/warning trigger system with recommended corrective procedures
- [ ] Add hazard detection and alternate route alerts for EVA navigation
- [ ] Add breadcrumb navigation tracking for return-to-rover (ingress)
- [ ] Expand the alias map in [src/main.py](src/main.py) for more telemetry field names and question phrasing
- [ ] Add comprehensive test suite for failure modes: missing fields, swapped labels, stale telemetry, malformed JSON, unit mismatches
