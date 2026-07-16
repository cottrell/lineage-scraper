#!/usr/bin/env python
import json
import logging
import re
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import argh
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

DEFAULT_FETCHER = "httpx"
DEFAULT_CACHE_ENABLED = True
DEFAULT_CACHE_REFRESH = False
DEFAULT_CACHE_DIR = Path.cwd() / "cache"
DEFAULT_CACHE_FILE = DEFAULT_CACHE_DIR / "pages.db"

DEFAULT_HEADLESS = False
DEFAULT_WAIT_MS = 2000
DEFAULT_MAX_DEPTH = 0
DEFAULT_OUTPUT_DIR = Path.cwd() / "data"
DEFAULT_DISPLAY_LIMIT = 100
DEFAULT_DELAY = 0.5

DEFAULT_BROWSER_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Cache-Control": "max-age=0",
}


class RateLimiter:
    def __init__(self, delay: float) -> None:
        self.base_delay = max(0.0, delay)
        self.delay = self.base_delay
        self.last_request_time = 0.0

    def acquire(self) -> None:
        if self.delay <= 0:
            return
        elapsed = time.monotonic() - self.last_request_time
        remaining = self.delay - elapsed
        if remaining > 0:
            time.sleep(remaining)
        self.last_request_time = time.monotonic()


def parse_crawl_delay(robots_text: str) -> float | None:
    try:
        lines = [line.strip().lower() for line in robots_text.splitlines()]
        current_agent_is_wildcard = False
        for line in lines:
            if line.startswith("user-agent:"):
                agent = line.split(":", 1)[1].strip()
                current_agent_is_wildcard = (agent == "*")
            elif line.startswith("crawl-delay:") and current_agent_is_wildcard:
                try:
                    return float(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
    except Exception:
        pass
    return None


def get_robots_crawl_delay(base_url: str, cfg: dict) -> float | None:
    if not base_url:
        return None
    if "robots_delays" not in cfg:
        cfg["robots_delays"] = {}
    if base_url in cfg["robots_delays"]:
        return cfg["robots_delays"][base_url]

    robots_url = urljoin(base_url, "/robots.txt")
    log.info(f"Checking robots.txt at {robots_url}")
    try:
        client = cfg.get("httpx_client")
        if client is None:
            import httpx
            headers = {**DEFAULT_BROWSER_HEADERS, "User-Agent": cfg["user_agent"]}
            resp = httpx.get(robots_url, headers=headers, timeout=10, follow_redirects=True)
        else:
            resp = client.get(robots_url, timeout=10)

        if resp.status_code == 200:
            delay = parse_crawl_delay(resp.text)
            if delay is not None:
                log.info(f"Found robots.txt Crawl-delay: {delay}s")
                cfg["robots_delays"][base_url] = delay
                return delay
    except Exception as e:
        log.debug(f"Could not fetch robots.txt: {e}")

    cfg["robots_delays"][base_url] = None
    return None


def is_captcha(html: str) -> bool:
    text = html.lower()
    if "attention required! | cloudflare" in text or "cf-challenge-error" in text:
        return True
    if "just a moment..." in text and "cloudflare" in text:
        return True
    if "verify you are human" in text and ("captcha" in text or "cloudflare" in text or "turnstile" in text):
        return True
    if "cf-turnstile-wrapper" in text:
        return True
    return False


def maybe_accept_cookies(page) -> None:
    selectors = [
        "button:has-text('Accept all cookies')",
        "button:has-text('Accept all')",
        "button:has-text('Accept')",
        "[aria-label*='Accept']",
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count():
                loc.click(timeout=2000)
                page.wait_for_timeout(200)
                return
        except Exception:
            continue


class Cache:
    def __init__(self, path: Path, enabled: bool, refresh: bool) -> None:
        self.path = path
        self.enabled = enabled
        self.refresh = refresh
        self.conn: sqlite3.Connection | None = None
        if self.enabled:
            self._ensure_conn()

    def _ensure_conn(self) -> sqlite3.Connection:
        if self.conn is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(self.path)
            self.conn.execute("CREATE TABLE IF NOT EXISTS pages (url TEXT PRIMARY KEY, payload TEXT, ts TEXT)")
            self.conn.execute("CREATE TABLE IF NOT EXISTS links (url TEXT PRIMARY KEY, payload TEXT, ts TEXT)")
        return self.conn

    def get(self, table: str, url: str) -> str | None:
        if not self.enabled or self.refresh:
            return None
        conn = self._ensure_conn()
        cur = conn.execute(f"SELECT payload FROM {table} WHERE url = ?", (url,))
        row = cur.fetchone()
        return row[0] if row else None

    def set(self, table: str, url: str, payload: str) -> None:
        if not self.enabled or payload is None:
            return
        conn = self._ensure_conn()
        conn.execute(
            f"INSERT OR REPLACE INTO {table} (url, payload, ts) VALUES (?, ?, ?)",
            (url, payload, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()

    def close(self) -> None:
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None


def fetch_with_playwright(url: str, cfg: dict) -> str:
    from playwright.sync_api import sync_playwright

    ctx = cfg.get("pw_ctx")
    if ctx is None:
        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=cfg["headless"])
        context = browser.new_context(user_agent=cfg["user_agent"])
        page = context.new_page()
        cfg["pw_ctx"] = {"pw": pw, "browser": browser, "context": context, "page": page}
    else:
        page = ctx["page"]

    page.goto(url, wait_until="networkidle", timeout=30000)
    maybe_accept_cookies(page)
    if cfg["wait_ms"]:
        page.wait_for_timeout(cfg["wait_ms"])
    html = page.content()
    page.goto("about:blank")
    return html


def fetch_with_httpx(url: str, cfg: dict) -> str:
    import httpx

    headers = {**DEFAULT_BROWSER_HEADERS, "User-Agent": cfg["user_agent"]}
    client = cfg.get("httpx_client")
    if client is None:
        client = httpx.Client(headers=headers, timeout=30, follow_redirects=True)
        cfg["httpx_client"] = client
    resp = client.get(url)
    resp.raise_for_status()
    return resp.text


def fetch_with_cloudscraper(url: str, cfg: dict) -> str:
    import cloudscraper

    scraper = cfg.get("cloudscraper_client")
    if scraper is None:
        scraper = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows", "mobile": False})
        scraper.headers.update({"User-Agent": cfg["user_agent"]})
        cfg["cloudscraper_client"] = scraper
    resp = scraper.get(url, timeout=30)
    resp.raise_for_status()
    return resp.text


def fetch_page(url: str, cfg: dict) -> str:
    cache: Cache = cfg["cache"]
    cached = cache.get("pages", url)
    if cached and not is_captcha(cached):
        log.debug(f"[cache] {url}")
        return cached

    limiter: RateLimiter = cfg.get("rate_limiter")
    if limiter:
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""
        robots_delay = get_robots_crawl_delay(base_url, cfg)
        if robots_delay is not None:
            limiter.delay = max(limiter.base_delay, robots_delay)
        else:
            limiter.delay = limiter.base_delay
        limiter.acquire()

    fetcher = cfg["fetcher"]
    try:
        if fetcher == "playwright":
            html = fetch_with_playwright(url, cfg)
        elif fetcher == "httpx":
            html = fetch_with_httpx(url, cfg)
        elif fetcher == "cloudscraper":
            html = fetch_with_cloudscraper(url, cfg)
        else:
            raise SystemExit(f"Unknown fetcher: {fetcher}")
    except Exception as e:
        log.warning(f"Fetch error {url}: {e}")
        return ""

    if html and not is_captcha(html):
        cache.set("pages", url, html)

    return html


def _looks_like_html(content: str) -> bool:
    start = content[:500].lower()
    return '<html' in start or '<!doctype' in start or '<head' in start or '<body' in start


def _extract_links_from_html(html: str, base_url: str) -> list[dict[str, str]]:
    if not _looks_like_html(html):
        return []
    soup = BeautifulSoup(html, "lxml")
    seen: set[str] = set()
    links: list[dict[str, str]] = []

    for tag in soup.find_all(href=True):
        href = str(tag.get("href", "")).strip()
        if not href:
            continue

        clean_href, _ = urldefrag(href)
        url = urljoin(base_url or "", clean_href)

        if url in seen:
            continue

        seen.add(url)
        text = tag.get_text(strip=True) if hasattr(tag, "get_text") else ""
        links.append({"url": url, "text": text, "raw_href": href})

    # Also pick up plain URLs in the document text (for cases where PDFs are embedded in script/content)
    for match in re.findall(r"https?://[^\s\"'>]+", html):
        if match in seen:
            continue
        seen.add(match)
        links.append({"url": match, "text": "", "raw_href": match})

    return links


def extract_links(page_url: str, html: str, cfg: dict) -> list[dict[str, str]]:
    cache: Cache = cfg["cache"]
    cached = cache.get("links", page_url)
    if cached:
        log.debug(f"[links cache] {page_url}")
        return json.loads(cached)

    links = _extract_links_from_html(html, cfg["base_url"])
    cache.set("links", page_url, json.dumps(links))
    return links


def infer_file_type(url: str, link_text: str) -> str:
    from urllib.parse import urlparse

    path = urlparse(url).path.lower()
    if "." in path:
        ext = "." + path.rsplit(".", 1)[-1]
        ext_map = {
            ".csv": "csv",
            ".tsv": "tsv",
            ".xls": "excel",
            ".xlsx": "excel",
            ".xlsm": "excel",
            ".json": "json",
            ".jsonl": "jsonl",
            ".ndjson": "jsonl",
            ".parquet": "parquet",
            ".pq": "parquet",
            ".xml": "xml",
            ".sqlite": "sqlite",
            ".sqlite3": "sqlite",
            ".db": "sqlite",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".pdf": "pdf",
        }
        ft = ext_map.get(ext)
        if ft:
            return ft

    patterns = [
        (r"exportreport\?", "csv"),
        (r"xmldatareport\?", "xml"),
        (r"pdfdatareport\?", "pdf"),
        (r"dataexport\?", "csv"),
        (r"\.csv($|\?)", "csv"),
        (r"\.json($|\?)", "json"),
        (r"\.xml($|\?)", "xml"),
        (r"\.xlsx?($|\?)", "excel"),
        (r"\.pdf($|\?)", "pdf"),
    ]
    lower = url.lower()
    for pattern, ft in patterns:
        if re.search(pattern, lower):
            return ft

    if "pdf" in link_text.lower():
        return "pdf"
    return "unknown"

def save_links(records: dict[str, dict], cfg: dict) -> None:
    """Save crawl results to output directory.

    Supports:
    - 'edge-node': nodes.json + edges.json
    - 'openlineage': openlineage.json
    """
    output_dir = cfg["output_dir"]
    output_format = cfg["output_format"]
    output_dir.mkdir(parents=True, exist_ok=True)

    if output_format == "edge-node":
        nodes_path = output_dir / "nodes.json"
        edges_path = output_dir / "edges.json"
        if cfg.get("include_parents_in_nodes", True):
            nodes = list(records.values())
        else:
            nodes = [{k: v for k, v in rec.items() if k != "parents"} for rec in records.values()]
        edges = []
        for rec in records.values():
            for parent in rec.get("parents", []):
                edges.append({"parent": parent, "child": rec["url"]})
        nodes_path.write_text(json.dumps(nodes, indent=2), encoding="utf-8")
        edges_path.write_text(json.dumps(edges, indent=2), encoding="utf-8")

    elif output_format == "openlineage":
        run_id = str(uuid.uuid4())

        parsed_start = urlparse(cfg["start_url"])
        start_ns = f"{parsed_start.scheme}://{parsed_start.netloc}" if parsed_start.scheme else "http://localhost"
        start_name = parsed_start.path + (f"?{parsed_start.query}" if parsed_start.query else "")
        if not start_name:
            start_name = "/"

        inputs = [{
            "namespace": start_ns,
            "name": start_name,
        }]

        outputs = []
        for url_str, rec in records.items():
            parsed = urlparse(url_str)
            ns = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme else "http://localhost"
            name = parsed.path + (f"?{parsed.query}" if parsed.query else "")
            if not name:
                name = "/"

            facets = {}
            if "file_type" in rec:
                facets["symlinks"] = {
                    "identifiers": [
                        {
                            "namespace": ns,
                            "name": name,
                            "type": "FILE"
                        }
                    ]
                }

            outputs.append({
                "namespace": ns,
                "name": name,
                "facets": facets
            })

        event = {
            "eventType": "COMPLETE",
            "eventTime": datetime.now(timezone.utc).isoformat(),
            "producer": "https://github.com/cottrell/lineage-scraper",
            "schemaURL": "https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/RunEvent",
            "job": {
                "namespace": "lineage-scraper",
                "name": f"crawl-{parsed_start.netloc or 'unknown'}"
            },
            "run": {
                "runId": run_id
            },
            "inputs": inputs,
            "outputs": outputs
        }

        ol_path = output_dir / "openlineage.json"
        ol_path.write_text(json.dumps(event, indent=2), encoding="utf-8")

    else:
        raise ValueError(f"Unknown output format: {output_format}")


@argh.arg("url", help="Full start URL to crawl")
@argh.arg("--depth", "-d", help="Max crawl depth (same domain)")
@argh.arg("--delay", help="Seconds between requests (respects robots.txt crawl-delay)")
@argh.arg("--wait-ms", help="Extra wait after page load")
@argh.arg("--no-cache", help="Disable cache")
@argh.arg("--refresh", help="Force refresh cache")
@argh.arg("--headless", help="Run browser headless")
@argh.arg("--output-dir", "-o", help="Output directory")
@argh.arg("--output-format", help="Output format: edge-node, openlineage")
@argh.arg("--no-parents-in-nodes", help="Exclude parents array from nodes.json")
@argh.arg("--fetcher", help="Fetcher backend: playwright, httpx, cloudscraper")
@argh.arg("--user-agent", help="User-Agent header")
@argh.arg("--cache-file", help="Path to cache file")
@argh.arg("-v", "--verbose", action="count", default=0, help="Verbosity: -v=info, -vv=debug")
def main(
    url: str,
    depth: int = DEFAULT_MAX_DEPTH,
    delay: float = DEFAULT_DELAY,
    wait_ms: int = DEFAULT_WAIT_MS,
    no_cache: bool = False,
    refresh: bool = False,
    headless: bool = False,
    output_dir: str = str(DEFAULT_OUTPUT_DIR),
    output_format: str = "edge-node",
    no_parents_in_nodes: bool = False,
    fetcher: str = DEFAULT_FETCHER,
    user_agent: str = DEFAULT_USER_AGENT,
    cache_file: str = str(DEFAULT_CACHE_FILE),
    verbose: int = 0,
) -> None:
    level = logging.WARNING if verbose == 0 else logging.INFO if verbose == 1 else logging.DEBUG
    logging.basicConfig(level=level, format="%(message)s")

    parsed_start = urlparse(url)
    base = f"{parsed_start.scheme}://{parsed_start.netloc}" if parsed_start.scheme and parsed_start.netloc else ""

    cfg = {
        "base_url": base,
        "start_path": "",
        "start_url": url,
        "max_depth": depth,
        "delay": delay,
        "rate_limiter": RateLimiter(delay),
        "wait_ms": wait_ms,
        "use_cache": not no_cache,
        "cache_refresh": refresh,
        "headless": headless,
        "output_dir": Path(output_dir),
        "output_format": output_format,
        "include_parents_in_nodes": not no_parents_in_nodes,
        "fetcher": fetcher.lower(),
        "pw_ctx": None,
        "user_agent": user_agent,
        "cache_file": Path(cache_file),
    }
    cfg["cache"] = Cache(cfg["cache_file"], enabled=cfg["use_cache"], refresh=cfg["cache_refresh"])

    records: dict[str, dict] = {}
    visited: set[str] = set()
    queue: list[tuple[str, int]] = [(cfg["start_url"], 0)]

    try:
        while queue:
            page_url, depth = queue.pop(0)
            if page_url in visited:
                continue
            visited.add(page_url)

            html = fetch_page(page_url, cfg)
            if not html:
                continue
            if is_captcha(html):
                log.warning("Captcha page encountered; rerun with --refresh and solve once in headful mode.")
                break
            links = extract_links(page_url, html, cfg)
            log.debug(f"[page] {page_url} -> {len(links)} links")

            for link in links:
                ext = infer_file_type(link["url"], link.get("text", ""))
                if ext != "unknown":
                    log.debug(f"[file] {ext}: {link['url']}")
                if link["url"] not in records:
                    record = {"url": link["url"], "parents": []}
                    if ext != "unknown":
                        record["file_type"] = ext
                    if link.get("text"):
                        record["link_text"] = link["text"]
                    records[link["url"]] = record
                if page_url not in records[link["url"]]["parents"]:
                    records[link["url"]]["parents"].append(page_url)

                if depth < cfg["max_depth"]:
                    parsed_start = urlparse(cfg["start_url"])
                    parsed = urlparse(link["url"])
                    if parsed.netloc == parsed_start.netloc:
                        queue.append((link["url"], depth + 1))

        save_links(records, cfg)
        log.info(f"Saved {len(records)} links to {cfg['output_dir']}")
        log.info(f"Crawl depth: {cfg['max_depth']}")
        if cfg["use_cache"]:
            state = "refreshed" if cfg["cache_refresh"] else "warm"
            log.info(f"Cache: {cfg['cache_file']} ({state})")
        else:
            log.info("Cache disabled")

    finally:
        ctx = cfg.get("pw_ctx")
        if ctx:
            try:
                ctx["page"].close()
            except Exception:
                pass
            try:
                ctx["browser"].close()
            except Exception:
                pass
            try:
                ctx["pw"].stop()
            except Exception:
                pass
            cfg["pw_ctx"] = None
        client = cfg.get("httpx_client")
        if client:
            try:
                client.close()
            except Exception:
                pass
            cfg["httpx_client"] = None
        scraper = cfg.get("cloudscraper_client")
        if scraper:
            try:
                scraper.close()
            except Exception:
                pass
            cfg["cloudscraper_client"] = None
        cache: Cache = cfg.get("cache")
        if cache:
            try:
                cache.close()
            except Exception:
                pass


def cli():
    argh.dispatch_command(main)


if __name__ == "__main__":
    cli()
