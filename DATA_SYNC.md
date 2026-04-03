# Data Synchronization Configuration

The EVA Assistant now fetches telemetry data directly from your HTTPS server every second (matching frontend behavior). Data is passed directly to the LLM for arithmetic calculations—no vector database or embeddings pipeline.

## How It Works

1. **Initialization**: On startup, [src/telemetry.py](src/telemetry.py) fetches telemetry data from your server
2. **Background Polling**: A daemon thread polls the server every 1 second (same frequency as frontend)
3. **Live Data**: Each question retrieves the latest telemetry data from the background thread
4. **LLM Processing**: Mistral performs arithmetic on current values
5. **Failover**: If server fetch fails, the thread continues retrying

## Architecture

```
Server (localhost:11434)
    ↓
/data/EVA.json, /data/ROVER.json, /data/LTV.json
    ↓
Background Thread (polls every 1 second)
    ↓
Global _current_telemetry (thread-safe)
    ↓
Main Thread → User Question
    ↓
LLM Arithmetic → Answer
```

## Configuration

Set environment variables to control data sync behavior:

### Server Configuration
```bash
# HTTPS server base URL (defaults to http://localhost:11434)
export TELEMETRY_SERVER_BASE="http://localhost:11434"
```

**Note**: Polling interval is hardcoded to 1 second in [src/telemetry.py](src/telemetry.py) to match frontend. Modify `POLL_INTERVAL_SECONDS` in the file to change.

## Usage

### Running the Assistant

```bash
# Start with default server
cd src
python3 main.py

# Custom server URL
export TELEMETRY_SERVER_BASE="http://custom-server:1234"
python3 main.py
```

## Data Structure

The system expects JSON files with this structure:

```json
{
  "telemetry": {
    "eva1": { "field1": "value1", "field2": "value2" },
    "eva2": { "field1": "value1", "field2": "value2" }
  },
  "dcu": { "eva1": { "device": "status" } },
  "imu": { "eva1": { "x": 0, "y": 0, "z": 0 } },
  "error": { "error_name": "status_value" },
  "uia": { "device_name": "status_value" }
}
```

## Background Thread Details

- **Polling interval**: 1 second (matches frontend `setInterval(fetchData(), 1000)`)
- **Daemon thread**: Runs in background and doesn't block app shutdown
- **Thread safety**: Uses `threading.Lock()` for safe data access
- **Error resilience**: Fetch failures logged but don't stop polling

### How to Access Current Data

In Python code:

```python
from telemetry import get_current_telemetry, format_telemetry_for_llm

# Get raw data dict
data = get_current_telemetry()

# Get formatted text for LLM
text = format_telemetry_for_llm(data)
```

## Logging

Set logging level to see data sync details:

```bash
# In terminal before running
export LOG_LEVEL=DEBUG

# Or in Python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Performance Notes

- **Consistent updates**: Every question sees data fetched within the last 1 second
- **No stale data**: Unlike vector DB approach, values are always current
- **Low overhead**: Simple HTTP fetches, no embedding calculations
- **Direct LLM access**: All telemetry visible to LLM (no retrieval ranking)

## Troubleshooting

**"Failed to fetch telemetry" errors:**
- Check server is running: `curl http://localhost:11434/data/EVA.json`
- Verify `TELEMETRY_SERVER_BASE` is correct
- Check network connectivity

**LLM returns "not provided":**
- Verify field exists in server JSON
- Check exact field name (case-sensitive)
- Look at debug logging to see fetched data structure

**Assistant starts but gives no responses:**
- Verify Ollama is running: `ollama serve`
- Check Mistral model is pulled: `ollama list`

