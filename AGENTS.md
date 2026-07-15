## CLI

`lineage_scraper.py` — single-file crawler, dumps links + inferred file types from a start URL.

```bash
uv run lineage_scraper.py <url> [--depth N] [--fetcher httpx|cloudscraper|playwright] [--output-format edge-node|openlineage] [-v]
```

Full flags: `uv run lineage_scraper.py --help`. Details: `README.md`.
Output: `data/nodes.json` + `data/edges.json` (default), or `data/openlineage.json` with `--output-format openlineage`.
Cache: SQLite at `cache/pages.db`, on by default (`--no-cache` / `--refresh`).

## Swarm

Swarm workflow: read first:
- Runtime map: `/tmp/nudge-swarm/lineage-scraper/runtime.json`
- Self-awareness note: `/tmp/nudge-swarm/lineage-scraper/self-awareness.txt`

Use as source of truth for:
- tmux pane targets
- monitor sockets, live state
- babysit pid/log/spec/state files

Swarm CLI: `aiswarm`
Prereq: `aiswarm` must be on `PATH`; install it with `make install-aiswarm`.

Messaging (durable, preferred):
- Use the comms log for reliability between agents: `aiswarm send <cfg> <pane> "msg"` or `log_broadcast`.
- Inspect: `aiswarm log <cfg> [--pending] [--pane 0.2]`, `aiswarm cursors <cfg>`.
- Direct/manual still works: `./tmux-send <target> "message"`.

Worker loop:
- `aiswarm start <cfg>` starts the base comms worker for `monitor: true` panes.
- The worker consumes the log and delivers via `tmux-send` when the pane is idle.
- Babysit prompt nudges are independent; use `aiswarm babysit start|stop <cfg>`.

Do NOT use raw `tmux send-keys ... Enter`.

Swarm scripts: `swarm/`.
