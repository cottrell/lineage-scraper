#!/usr/bin/env python
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urldefrag, urlparse

import argh
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

DEFAULT_BASE_URL = "https://www.dmo.gov.uk"
DEFAULT_START_PATH = "/data/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

CACHE_DEFAULT_FETCHER = os.getenv("DMO_FETCH", "playwright").lower()
CACHE_DEFAULT_ENABLED = os.getenv("DMO_CACHE", "1").lower() not in {"0", "false", "no"}
CACHE_DEFAULT_REFRESH = os.getenv("DMO_REFRESH", "0").lower() not in {"0", "false", "no"}
CACHE_DIR = Path(os.getenv("DMO_CACHE_DIR", "cache"))
CACHE_FILE = CACHE_DIR / "dmo_data_page.html"

HEADLESS_DEFAULT = os.getenv("DMO_HEADLESS", "0").lower() in {"1", "true", "yes"}
WAIT_MS_DEFAULT = int(os.getenv("DMO_WAIT_MS", "2000"))
MAX_DEPTH_DEFAULT = int(os.getenv("DMO_DEPTH", "0"))

DEFAULT_OUTPUT_PATH = Path("dmo_data/links.json")


def is_captcha(html: str) -> bool:
    text = html.lower()
    return "captcha" in text or "shield" in text


def maybe_accept_cookies(page) -> bool:
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
                page.wait_for_timeout(300)
                return True
        except Exception:
            continue
    return False


def fetch_with_playwright(url: str, cfg: dict) -> str:
    ctx = cfg.get("pw_ctx")
    pw_owned = False
    if ctx is None:
        pw = sync_playwright().start()
        browser = pw.chromium.launch(headless=cfg["headless"])
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()
        cfg["pw_ctx"] = {"pw": pw, "browser": browser, "context": context, "page": page}
        pw_owned = True
    else:
        page = ctx["page"]

    page.goto(url, wait_until="networkidle", timeout=30000)
    maybe_accept_cookies(page)
    if cfg["wait_ms"]:
        page.wait_for_timeout(cfg["wait_ms"])
    html = page.content()
    if pw_owned is False:
        page.goto("about:blank")
    else:
        # will be closed at shutdown
        pass

    return html


def fetch_page(url: str, cfg: dict) -> str:
    use_cache = cfg["use_cache"] and url == cfg["start_url"]
    if use_cache and CACHE_FILE.exists() and not cfg["cache_refresh"]:
        cached = CACHE_FILE.read_text(encoding="utf-8", errors="ignore")
        if not is_captcha(cached):
            print(f"Cache hit: {CACHE_FILE}")
            return cached

    fetcher = cfg["fetcher"]
    if fetcher == "playwright":
        html = fetch_with_playwright(url, cfg)
    else:
        raise SystemExit(f"Unknown fetcher: {fetcher}")

    if use_cache and not is_captcha(html):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(html, encoding="utf-8")
        state = "refreshed" if cfg["cache_refresh"] else "warm"
        print(f"Cache write: {CACHE_FILE} ({state})")

    return html


def extract_links(html: str, base_url: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    seen: set[str] = set()
    links: list[dict[str, str]] = []

    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if not href:
            continue

        clean_href, _ = urldefrag(href)
        url = urljoin(base_url, clean_href)

        if url in seen:
            continue

        seen.add(url)
        links.append({"url": url, "text": tag.get_text(strip=True)})

    return links


def save_links(links: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(links, indent=2), encoding="utf-8")


@argh.arg("--base-url", help="Base site URL")
@argh.arg("--start-path", help="Start path relative to base (default /data/)")
@argh.arg("--depth", "-d", help="Max crawl depth (same domain)")
@argh.arg("--wait-ms", help="Extra wait after page load")
@argh.arg("--no-cache", help="Disable cache")
@argh.arg("--refresh", help="Force refresh cache")
@argh.arg("--headless", help="Run browser headless")
@argh.arg("--output", help="Output JSON path")
@argh.arg("--fetcher", help="Fetcher backend (playwright by default)")
def main(
    base_url: str | None = None,
    start_path: str | None = None,
    depth: int | None = None,
    wait_ms: int | None = None,
    no_cache: bool = False,
    refresh: bool = False,
    headless: bool = False,
    output: str | None = None,
    fetcher: str | None = None,
) -> None:
    base = (base_url or DEFAULT_BASE_URL).rstrip("/")
    start = start_path if start_path else DEFAULT_START_PATH
    start = start if start.startswith("/") else f"/{start}"
    cfg = {
        "base_url": base,
        "start_path": start,
        "start_url": f"{base}{start}",
        "max_depth": int(depth) if depth is not None else MAX_DEPTH_DEFAULT,
        "wait_ms": wait_ms if wait_ms is not None else WAIT_MS_DEFAULT,
        "use_cache": False if no_cache else CACHE_DEFAULT_ENABLED,
        "cache_refresh": True if refresh else CACHE_DEFAULT_REFRESH,
        "headless": True if headless else HEADLESS_DEFAULT,
        "output_path": Path(output) if output else DEFAULT_OUTPUT_PATH,
        "fetcher": (fetcher or CACHE_DEFAULT_FETCHER).lower(),
        "pw_ctx": None,
    }

    session_id = uuid.uuid4().hex[:8]
    crawl_ts = datetime.now(timezone.utc).isoformat()
    records: list[dict[str, object]] = []

    visited: set[str] = set()
    queue: list[tuple[str, int]] = [(cfg["start_url"], 0)]

    while queue:
        page_url, depth = queue.pop(0)
        if page_url in visited:
            continue
        visited.add(page_url)

        html = fetch_page(page_url, cfg)
        if is_captcha(html):
            print("Captcha page encountered; rerun with DMO_REFRESH=1 and headful mode to solve.")
            break
        links = extract_links(html, cfg["base_url"])

        for link in links:
            record_id = f"{session_id}-{uuid.uuid4().hex[:8]}"
            parsed = urlparse(link["url"])
            ext = Path(parsed.path).suffix.lstrip(".").lower() or "unknown"
            records.append(
                {
                    "id": record_id,
                    "url": link["url"],
                    "file_type": ext,
                    "provenance": {
                        "discovered_from": page_url,
                        "crawl_timestamp": crawl_ts,
                        "crawl_session_id": session_id,
                        "link_text": link["text"],
                        "link_context": None,
                    },
                    "download_info": None,
                    "tags": [],
                    "notes": None,
                }
            )

            if depth < cfg["max_depth"]:
                parsed_start = urlparse(cfg["start_url"])
                if parsed.netloc == parsed_start.netloc:
                    queue.append((link["url"], depth + 1))

    save_links(records, cfg["output_path"])
    print(f"Saved {len(records)} links to {cfg['output_path']}")
    print(f"Crawl depth: {cfg['max_depth']}")
    if cfg["use_cache"]:
        state = "refreshed" if cfg["cache_refresh"] else "warm"
        print(f"Cache: {CACHE_FILE} ({state})")
    else:
        print("Cache disabled")

    ctx = cfg.get("pw_ctx")
    if ctx:
        try:
            ctx["page"].close()
        except Exception:
            pass
        ctx["browser"].close()
        ctx["pw"].stop()
        cfg["pw_ctx"] = None


if __name__ == "__main__":
    argh.dispatch_command(main)
