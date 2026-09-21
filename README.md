# NanoJev MCP
[简体中文](README_CN.md)|[English](README.md)

Wraps [NanoJev](https://github.com/TianyuCodings/NanoJev)'s decision service as an MCP server, letting any MCP-capable agent (Claude Code, ccwitch, Cline, Cursor, ...) query the NanoJev model in natural language.

```
agent ──stdio(MCP)──> mcp_nanojev.py ──HTTP──> NanoJev repo's serve_decisions.py :8765 (model loaded once)
```

The MCP process is a thin proxy that never loads the model; multiple agents can share the same inference service simultaneously.

## Prerequisite: Install NanoJev

```bash
git clone https://github.com/TianyuCodings/NanoJev.git
cd NanoJev
python -m pip install -r requirements-toy.txt huggingface_hub
```

Download the checkpoint (~2.3 GB; see the NanoJev README for details):

```python
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="C-Tianyu/NanoJev",
    revision="unified-games-v1",
    local_dir="checkpoints/NanoJev-unified",
    allow_patterns=["best.safetensors", "config.json", "tokenizer/*", "backbone_config/*"],
)
```

## Setup

**1. Download this package** (clone / unzip to any directory, e.g. `D:\nanojev_mcp`)

**2. One-command configuration**

```bash
python setup_mcp.py
```

The script will: install the `mcp` SDK -> probe the inference service -> register `nanojev` into Claude Code (user scope) -> print JSON for other clients. Common options:

```bash
python setup_mcp.py --service-url http://127.0.0.1:9000/api/evaluate   # non-default port
python setup_mcp.py --python D:\NanoJev\.venv\Scripts\python.exe       # use NanoJev's venv
python setup_mcp.py --skip-claude                                      # only print JSON, leave claude config untouched
```

**3. Start the NanoJev inference service** (in the NanoJev repo directory)

```bash
python scripts/serve_decisions.py --checkpoint-dir checkpoints/NanoJev-unified --web-root web --port 8765 --disable-native-triton
```

Done. Just ask your agent in natural language, e.g.:

> Use nanojev to decide: the agent is at (2,2), is the cell to the north passable? Which of the four directions is the best move?

## Running Directly (stdio)

The MCP server uses the **stdio transport** (JSON-RPC over stdin/stdout) and listens on no port. Launch it directly with:

```bash
python mcp_nanojev.py                    # default service URL http://127.0.0.1:8765/api/evaluate
```

Override the service URL with the `NANOJEV_EVALUATE_URL` environment variable:

```bash
# Linux / macOS
NANOJEV_EVALUATE_URL=http://127.0.0.1:9000/api/evaluate python mcp_nanojev.py
# Windows PowerShell
$env:NANOJEV_EVALUATE_URL = "http://127.0.0.1:9000/api/evaluate"; python mcp_nanojev.py
```

Agents spawn it as a subprocess and communicate over stdin/stdout; when run standalone the terminal only shows raw JSON-RPC traffic. Ctrl+C to exit.

## Manual MCP Client Configuration

If you prefer to register manually (or use a client other than Claude Code), copy [`config.json`](config.json) and adjust the paths:

```json
{
  "mcpServers": {
    "nanojev": {
      "command": "python",
      "args": ["D:\\nanojev_mcp\\mcp_nanojev.py"],
      "env": {
        "NANOJEV_EVALUATE_URL": "http://127.0.0.1:8765/api/evaluate"
      }
    }
  }
}
```

- **command** — path to a Python interpreter that has the `mcp` package installed.
- **args** — absolute path to `mcp_nanojev.py` in this package.
- **env.NANOJEV_EVALUATE_URL** — (optional) override the default service URL `http://127.0.0.1:8765/api/evaluate`.

Drop this into your client's config file:

| Client | Config file |
|---|---|
| Claude Desktop | `claude_desktop_config.json` |
| Cursor | `.cursor/mcp.json` |
| Cline | `cline_mcp_settings.json` |

## Tools Available to the Agent

| Tool | Input | Output |
|---|---|---|
| `nanojev_evaluate` | `state` (observation text) + `questions` (list of boolean / choice / score) | Per-question probability distributions, argmax verdicts, inference time |
| `nanojev_health` | — | Whether the inference service is ready |

## Four Decision-Loop Stages Where the Agent Uses the Model

1. **Feasibility gate (Boolean)** — Before moving, ask per-direction "is one cell north passable?" to prune illegal actions first.
2. **Action selection (Choice)** — Choose the next step from candidate actions; a single forward pass returns the full distribution over 2-255 candidates.
3. **Risk / urgency (Score)** — Ask "how urgent is it to change direction?" (0-3); set a threshold on the expected score to turn it into a rule.
4. **Look-ahead planning (Boolean + Choice)** — Batch-encode future states from candidate action sequences into a single `nanojev_evaluate` call, compare branch scores, then commit.

See [docs/MCP.md](docs/MCP.md) for more examples and troubleshooting. When not using an agent, you can also use the interactive terminal client:

```bash
python ask_nanojev.py
```
