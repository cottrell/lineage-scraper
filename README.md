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
- `--config` path to config JSON file for headers/cookies (loads `config.json` in current directory by default if it exists)
- `-v/-vv` verbosity: info / debug

Run `python lineage_scraper.py --help` for the full generated help text.

## Configuration File

You can use a local JSON configuration file (e.g., `config.json` in the current working directory, or via `--config <path>`) to configure custom headers and cookies globally or per-strategy.

### Format Example
```json
{
  "global": {
    "headers": {
      "X-Custom-Global-Header": "foo"
    },
    "cookies": {
      "session_id": "xyz123"
    }
  },
  "httpx": {
    "headers": {
      "User-Agent": "MyCustomHttpxAgent/1.0",
      "X-Httpx-Specific": "bar"
    }
  }
}
```

### Precedence
1. **User-Agent**: CLI `--user-agent` (if explicitly provided) > Fetcher-specific config `headers["User-Agent"]` > Global config `headers["User-Agent"]` > Default browser User-Agent.
2. **Headers**: Default browser headers < Global config headers < Fetcher-specific config headers.
3. **Cookies**: Global config cookies < Fetcher-specific config cookies.

### Security Guidance for Cookies
Since the config file can store sensitive authentication session cookies/tokens, it should not be committed to version control. On UNIX-like systems, ensure appropriate file permissions are set so other users cannot read the file:
```bash
chmod 600 config.json
```
If the config contains cookies and is group- or world-readable, a warning will be logged.

### Interaction with Caching and Rate Limiting
- **Caching**: Page requests are cached by URL. If you modify headers or cookies in the config (e.g., updating an expired session cookie), you must bypass cache reads by running with `--refresh` or disable caching with `--no-cache` to ensure the scraper sends the new credentials.
- **Rate Limiting**: Custom headers and cookies (such as API keys or valid browser-like cookies) may change how target sites rate limit or block requests. Combining these with the `--delay` parameter helps mimic authentic traffic patterns and prevent CAPTCHAs.

## Caching

- SQLite at `cache/pages.db` (HTML and extracted links per URL).
- Cache is on by default; use `--no-cache` to disable or `--refresh` to bypass reads.

