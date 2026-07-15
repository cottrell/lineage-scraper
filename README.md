# lineage-scraper (simple)

Single-file crawler to dump all links (with inferred file types) starting from a URL. Caches HTML and extracted links in SQLite to avoid re-fetching.

## Install

```bash
uv pip install argh beautifulsoup4 lxml httpx cloudscraper  # playwright optional
```

## Usage

```bash
# basic crawl (httpx, cached, depth 0)
python lineage_scraper.py https://example.org/page

# depth and logging
python lineage_scraper.py https://www.royalgreenwich.gov.uk/info/200167/budgets_and_spending \
  --fetcher httpx --depth 2 -v

# force fresh fetch, no cache
python lineage_scraper.py https://example.org/page --refresh --no-cache
```

Output (`edge-node` format, default): `data/nodes.json` + `data/edges.json`.

Node record:

```json
{
  "url": "https://example.org/file.pdf",
  "parents": ["https://example.org/page"],
  "file_type": "pdf",
  "link_text": "Some link text"
}
```

Edge record: `{"parent": "...", "child": "..."}`.

Use `--output-format openlineage` to emit an [OpenLineage](https://openlineage.io/) `RunEvent` (`data/openlineage.json`) instead.

## Options (flags)

- `--depth/-d` max same-domain crawl depth (default 0)
- `--delay` seconds between requests; respects `robots.txt` `Crawl-delay` if stricter (default 0.5)
- `--fetcher/-f` `httpx` (default), `cloudscraper`, `playwright`
- `--wait-ms/-w` extra wait after page load (playwright)
- `--headless` run playwright headless
- `--no-cache` disable cache
- `--refresh/-r` bypass cache reads (still writes)
- `--cache-file/-c` path to SQLite cache (default `cache/pages.db`)
- `--output-dir/-o` output directory (default `data/`)
- `--output-format` `edge-node` (default) or `openlineage`
- `--no-parents-in-nodes` exclude `parents` array from `nodes.json`
- `--user-agent/-u` User-Agent header
- `-v/-vv` verbosity: info / debug

Run `python lineage_scraper.py --help` for the full generated help text.

## Caching

- SQLite at `cache/pages.db` (HTML and extracted links per URL).
- Cache is on by default; use `--no-cache` to disable or `--refresh` to bypass reads.

## Legacy

Previous async crawler and related files are archived under `old/`.
