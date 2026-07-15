import json
from pathlib import Path

from lineage_scraper import (
    Cache,
    RateLimiter,
    infer_file_type,
    parse_crawl_delay,
    save_links,
)


def test_infer_file_type_patterns():
    assert infer_file_type("https://x/exportreport?foo=1", "") == "csv"
    assert infer_file_type("https://x/xmldatareport?foo=1", "") == "xml"
    assert infer_file_type("https://x/pdfdatareport?foo=1", "") == "pdf"
    assert infer_file_type("https://x/dataexport?foo=1", "") == "csv"
    assert infer_file_type("https://x/path/report.pdf", "") == "pdf"
    assert infer_file_type("https://x/path/report", "see PDF here") == "pdf"
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
