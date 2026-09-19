import json
from pathlib import Path

from lineage_scraper import (
    DEFAULT_BROWSER_HEADERS,
    Cache,
    RateLimiter,
    infer_file_type,
    parse_crawl_delay,
    save_links,
)


def test_default_browser_headers_no_accept_encoding():
    assert "Accept-Encoding" not in DEFAULT_BROWSER_HEADERS


def test_infer_file_type_patterns():
    assert infer_file_type("https://x/exportreport?foo=1", "") == "csv"
    assert infer_file_type("https://x/xmldatareport?foo=1", "") == "xml"
    assert infer_file_type("https://x/pdfdatareport?foo=1", "") == "pdf"
    assert infer_file_type("https://x/dataexport?foo=1", "") == "csv"
    assert infer_file_type("https://x/path/report.pdf", "") == "pdf"
    assert infer_file_type("https://x/path/report", "see PDF here") == "pdf"
    assert infer_file_type("https://x/path/archive.zip", "") == "zip"
    assert infer_file_type("https://x/path/archive.tar", "") == "tar"
    assert infer_file_type("https://x/path/archive.gz", "") == "gzip"
    assert infer_file_type("https://x/path/archive.tgz", "") == "tar"
    assert infer_file_type("https://x/path/archive.7z", "") == "7z"
    assert infer_file_type("https://x/download?file=data.zip", "") == "zip"
    assert infer_file_type("https://x/path/bundle", "Download ZIP archive") == "zip"
    assert infer_file_type("https://x/path/report", "") == "unknown"


def test_cache_roundtrip(tmp_path: Path):
    db = tmp_path / "cache.db"
    cache = Cache(db, enabled=True, refresh=False)

    url = "https://example.com/page"
    html = "<html></html>"
    cache.set("pages", url, html)
    assert cache.get("pages", url) == html

    links = [{"url": "https://example.com/file.csv", "text": "file"}]
    cache.set("links", url, json.dumps(links))
    assert cache.get("links", url) == json.dumps(links)

    cache.close()


def test_parse_crawl_delay():
    robots_txt = """
    User-agent: *
    Disallow: /private
    Crawl-delay: 3.5
    """
    assert parse_crawl_delay(robots_txt) == 3.5

    robots_txt_other = """
    User-agent: googlebot
    Crawl-delay: 1.0
    User-agent: *
    Crawl-delay: 2.0
    """
    assert parse_crawl_delay(robots_txt_other) == 2.0


def test_rate_limiter_acquire():
    import time
    limiter = RateLimiter(0.1)
    t0 = time.monotonic()
    limiter.acquire()
    limiter.acquire()
    t1 = time.monotonic()
    assert (t1 - t0) >= 0.09


def test_save_links_openlineage(tmp_path: Path):
    cfg = {
        "output_dir": tmp_path,
        "output_format": "openlineage",
        "start_url": "https://example.com/start",
    }
    records = {
        "https://example.com/file.pdf": {
            "url": "https://example.com/file.pdf",
            "file_type": "pdf",
            "link_text": "View PDF"
        }
    }
    save_links(records, cfg)

    ol_file = tmp_path / "openlineage.json"
    assert ol_file.exists()

    data = json.loads(ol_file.read_text(encoding="utf-8"))
    assert data["eventType"] == "COMPLETE"
    assert data["producer"] == "https://github.com/cottrell/lineage-scraper"
    assert data["inputs"][0]["namespace"] == "https://example.com"
    assert data["inputs"][0]["name"] == "/start"
    assert data["outputs"][0]["namespace"] == "https://example.com"
    assert data["outputs"][0]["name"] == "/file.pdf"
    assert data["outputs"][0]["facets"]["symlinks"]["identifiers"][0]["type"] == "FILE"


def test_get_robots_crawl_delay():
    from lineage_scraper import get_robots_crawl_delay

    class FakeResponse:
        def __init__(self, text, status_code=200):
            self.text = text
            self.status_code = status_code

    class FakeClient:
        def __init__(self, text):
            self.text = text
        def get(self, url, timeout=None):
            return FakeResponse(self.text)

    cfg = {
        "httpx_client": FakeClient("User-agent: *\nCrawl-delay: 5.0\n"),
        "user_agent": "test",
    }

    # First check fetches and parses
    delay = get_robots_crawl_delay("https://test.domain", cfg)
    assert delay == 5.0
    assert cfg["robots_delays"]["https://test.domain"] == 5.0

    # Second check uses cache
    cfg["httpx_client"] = None  # ensure no call is made
    delay2 = get_robots_crawl_delay("https://test.domain", cfg)
    assert delay2 == 5.0


def test_fetch_page_limiter_reset(tmp_path: Path):
    from lineage_scraper import fetch_page, Cache

    class FakeClient:
        def get(self, url, timeout=None):
            class FakeResponse:
                status_code = 404
                text = ""
            return FakeResponse()

    # Create dummy database to avoid real filesystem dependency
    db = tmp_path / "cache_test.db"
    cache = Cache(db, enabled=True, refresh=False)

    limiter = RateLimiter(0.1)
    cfg = {
        "cache": cache,
        "rate_limiter": limiter,
        "robots_delays": {
            "https://domain-with-robots": 5.0,
            "https://domain-without-robots": None
        },
        "fetcher": "httpx",
        "httpx_client": FakeClient(),
    }

    # Fetch from domain-with-robots -> delay should be 5.0
    fetch_page("https://domain-with-robots/page", cfg)
    assert limiter.delay == 5.0

    # Fetch from domain-without-robots -> delay should reset to 0.1 (base_delay)
    fetch_page("https://domain-without-robots/page", cfg)
    assert limiter.delay == 0.1

    cache.close()


def test_config_handling(tmp_path: Path):
    from lineage_scraper import load_config, resolve_fetcher_params, DEFAULT_USER_AGENT

    # Write a test config.json
    cfg_file = tmp_path / "config.json"
    cfg_content = {
        "global": {
            "headers": {
                "User-Agent": "GlobalBot/1.0",
                "X-Global-Header": "yes"
            },
            "cookies": {
                "session": "global-sess-id"
            }
        },
        "httpx": {
            "headers": {
                "User-Agent": "HttpxBot/2.0",
                "X-Httpx-Header": "httpx-specific"
            },
            "cookies": {
                "session": "httpx-sess-id",
                "httpx-only": "cookie-val"
            }
        }
    }
    cfg_file.write_text(json.dumps(cfg_content), encoding="utf-8")

    # 1. Test load_config
    loaded = load_config(cfg_file)
    assert loaded["global"]["cookies"]["session"] == "global-sess-id"

    # 2. Test resolve_fetcher_params merging and precedence
    # A. Case where user-agent is NOT overridden by CLI (so config specific UA wins)
    headers, cookies, ua = resolve_fetcher_params("httpx", DEFAULT_USER_AGENT, loaded)
    assert ua == "HttpxBot/2.0"
    assert headers["User-Agent"] == "HttpxBot/2.0"
    assert headers["X-Global-Header"] == "yes"
    assert headers["X-Httpx-Header"] == "httpx-specific"
    assert cookies["session"] == "httpx-sess-id"
    assert cookies["httpx-only"] == "cookie-val"

    # B. Case where user-agent is overridden by CLI
    headers_cli, cookies_cli, ua_cli = resolve_fetcher_params("httpx", "CLI-UA/3.0", loaded)
    assert ua_cli == "CLI-UA/3.0"
    assert headers_cli["User-Agent"] == "CLI-UA/3.0"

    # C. Check playwright specific domain conversion
    # Verify how playwright converts dict cookies
    # We can test that manually, but let's test resolve_fetcher_params for playwright
    headers_pw, cookies_pw, ua_pw = resolve_fetcher_params("playwright", DEFAULT_USER_AGENT, loaded)
    # playwright has no overrides, so it falls back to global
    assert ua_pw == "GlobalBot/1.0"
    assert headers_pw["User-Agent"] == "GlobalBot/1.0"
    assert cookies_pw["session"] == "global-sess-id"

