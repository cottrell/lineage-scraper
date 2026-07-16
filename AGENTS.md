## CLI

`lineage_scraper.py` — single-file crawler, dumps links + inferred file types from a start URL.

```bash
uv run lineage_scraper.py <url> [--depth N] [--fetcher httpx|cloudscraper|playwright] [--output-format edge-node|openlineage] [-v]
```

Full flags: `uv run lineage_scraper.py --help`. Details: `README.md`.
Output: `data/nodes.json` + `data/edges.json` (default), or `data/openlineage.json` with `--output-format openlineage`.
Cache: SQLite at `cache/pages.db`, on by default (`--no-cache` / `--refresh`).

<!-- AISWARM/NUDGE GUIDELINES START -->
## Swarm

Swarm CLI: `aiswarm` (on PATH; `make install-aiswarm` from the nudge repo).

Read workflow first:
- `aiswarm` — common commands cheat sheet
- `aiswarm instructions overview` — required agent briefing
- `aiswarm instructions handoff` / `tasks` — peer send and backlog dispatch
- `aiswarm this` — this swarm's config + runtime.json path

After start, machine map (not git): `/tmp/nudge-swarm/lineage-scraper/runtime.json`

Config: `.aiswarm/config.yaml` (cwd walk-up), `$AISWARM_CONFIG`, or explicit path.
Messaging: `aiswarm send <pane> "msg"` (durable log). Do NOT raw `tmux send-keys`.
<!-- AISWARM/NUDGE GUIDELINES END -->
