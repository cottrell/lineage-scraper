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

<!-- BACKLOG.MD GUIDELINES START -->
<!-- backlog.md-instructions-version: 1.51.0 -->
<CRITICAL_INSTRUCTION>

## Backlog.md Workflow

This project uses Backlog.md for task and project management.

**At the beginning of each conversation in this project, run `backlog instructions overview` before answering or taking action. Re-read it only if you have not read it yet in the current conversation.**

Use the overview to decide whether to search, read, create, or update Backlog tasks.

Before task lifecycle actions, read the matching detailed guide:
- `backlog instructions task-creation` before creating or splitting tasks
- `backlog instructions task-execution` before planning, changing status or assignee, adding a plan or implementation notes, or implementing task work
- `backlog instructions task-finalization` before checking acceptance criteria, writing final summaries, or moving tasks to terminal statuses

Use `backlog <command> --help` before running unfamiliar commands. Help shows options, fields, and examples.

Do not edit Backlog task, draft, document, decision, or milestone markdown files directly. Use the `backlog` CLI so metadata, relationships, and history stay consistent.

</CRITICAL_INSTRUCTION>
<!-- BACKLOG.MD GUIDELINES END -->
