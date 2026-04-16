# EVA Assistant
Local telemetry assistant that fetches live data from an HTTP server and performs field lookup and arithmetic in Python.

## Prerequisites
* Python 3.8+
* pip (Python package installer)
* Requests library installed from `requirements.txt`

## Dependencies
* **Requests**
  * HTTP library for fetching telemetry from the server

See [requirements.txt](requirements.txt) for the full list.

## Architecture

The EVA Assistant uses a direct data access approach with no vector database:

1. Background Polling - Fetches telemetry from the server every second
2. Live Data - Keeps the latest server snapshot in memory for each source file
3. Code-Based Arithmetic - `main.py` resolves fields and computes numeric answers in Python
4. Deterministic Formatting - Returned values are formatted directly in code
5. Thread-Safe - Background thread and main thread coordinate via locks

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
3. Format the final response directly in code

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
┌─ Background Thread ──────────────────────┐
│ Every 1 second:                          │
│ Fetch EVA.json, ROVER.json, LTV.json     │
│ Store each file as a separate snapshot    │
└──────────────────────────────────────────┘
                ↓
          User Question
                ↓
      get_current_telemetry()
                ↓
     resolve_question() / arithmetic in code
                ↓
         format_answer()
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

## Future Enhancements

- [ ] Add a post-answer verifier that checks the formatted text still matches the computed numeric value
- [ ] Add tests for the failure modes that matter most. Focus on missing fields, swapped labels, stale telemetry, malformed JSON, and unit mismatches in the files under tests
- [ ] Expand the alias map in [src/main.py](src/main.py) for more telemetry field names and question phrasing
- [ ] Consider a more formal schema or rules table if the telemetry format expands further
