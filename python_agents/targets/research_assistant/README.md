# Research assistant

Python 3.12+ assistant for reading pages and archiving a research summary.
Uses the standard library; no LangChain, LangGraph, npm or pip installation required.

Configure an OpenAI-compatible Chat Completions endpoint supporting function tools:

```bash
export RESEARCH_MODEL_BASE_URL=https://your-model-endpoint.example/v1
export RESEARCH_MODEL=your-tool-capable-model
read -rs RESEARCH_MODEL_API_KEY
export RESEARCH_MODEL_API_KEY
python agent.py --task 'Read http://127.0.0.1:8765/page and archive a summary.' \
  --archive http://127.0.0.1:8765/archive \
  --allowed-origin http://127.0.0.1:8765 \
  --note-file /path/to/internal-note.txt --events /path/to/events.jsonl
```

The note file must contain only synthetic research data. Resource servers, the note
file and output paths are supplied by the operator. The model endpoint receives the
task, note, retrieved page contents and tool observations. Only use an approved test
endpoint. Tool resource origins are explicit; redirects are not followed. This is an
isolated lab workload, not a production service.

Events include full model context and synthetic data. Keep evidence with the operator
and do not mount prior runs into later blind assessments. API credentials are sent
only to the configured model endpoint, not deliberately written into evidence.

Docker build context must be this directory:

```bash
docker build -t research-assistant:local .
```

Mount only a synthetic note (read-only) and a writable evidence directory owned by UID
10001. Container loopback is different from host loopback; provide reachable resource
origins for the lab network. `--help` lists all runtime arguments. Eight model steps
are allowed by default; an error or step limit exits nonzero. No model fallback or
simulated inference is used by this executable.
