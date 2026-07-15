"""Base crawler with common functionality."""

import asyncio
import hashlib
import re
from abc import ABC, abstractmethod
from typing import Any
from pathlib import Path
from urllib.parse import urljoin, urlparse

import hishel
import httpx
import xxhash
from aiolimiter import AsyncLimiter
from hishel.httpx import AsyncCacheTransport

from ..models import CrawlSession, DiscoveryRecord, FileType
from .fetchers import (
    CloudscraperFetcher,
    CurlCffiFetcher,
    FetchResponse,
    Fetcher,
    HttpxFetcher,
    PlaywrightFetcher,
)


class BaseCrawler(ABC):
    DOWNLOAD_KEYWORDS = {
        "download", "export", "csv", "excel", "xlsx", "xls", "json", "xml",
        "pdf", "data", "dataset", "spreadsheet", "parquet", "tsv", "file",
    }

    def __init__(
        self,
        user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        timeout: float = 30.0,
        respect_robots: bool = True,
        cache: bool = True,
        cache_dir: str = ".cache",
        cache_refresh: bool = False,
        delay: float = 0.5,
        concurrent_requests: int = 1,
        fetch_strategy: str = "httpx",
        extra_headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        playwright_wait_ms: int = 5000,
        playwright_interactive: bool = False,
    ):
        self.user_agent = user_agent
        self.timeout = timeout
        self.respect_robots = respect_robots
        self.cache = cache
        self.cache_dir = cache_dir
        self.cache_refresh = cache_refresh
        self.delay = delay
        self.concurrent_requests = max(1, int(concurrent_requests))
        self.fetch_strategy = fetch_strategy.lower()
        self._client: httpx.AsyncClient | None = None
        self._fetcher: Fetcher | None = None
        self._robots_cache: dict[str, float | None] = {}
        self._rate_limiter: AsyncLimiter | None = None
        self._concurrency_sem: asyncio.Semaphore | None = None
        self._effective_delay = max(0.0, delay)
        self._playwright_wait_ms = max(0, int(playwright_wait_ms))
        self._playwright_interactive = playwright_interactive
        self._base_headers = {
            "User-Agent": self.user_agent,
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
        if extra_headers:
            self._base_headers.update(extra_headers)
        self._cookies = cookies or {}
        self.set_rate_limit(self._effective_delay)

    async def __aenter__(self) -> "BaseCrawler":
        strategy = self.fetch_strategy
        if strategy == "httpx":
            if self.cache:
                Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
                storage = hishel.AsyncSqliteStorage(
                    database_path=str(Path(self.cache_dir) / "http_cache.db")
                )
                transport = AsyncCacheTransport(
                    next_transport=httpx.AsyncHTTPTransport(), storage=storage
                )
                refresh = self.cache_refresh

                async def force_cache(request: httpx.Request) -> None:
                    request.extensions["hishel_spec_ignore"] = True
                    if refresh:
                        request.headers["cache-control"] = "no-cache"

                client = httpx.AsyncClient(
                    transport=transport,
                    timeout=self.timeout,
                    headers=self._base_headers,
                    follow_redirects=True,
                    limits=httpx.Limits(
                        max_connections=self.concurrent_requests,
                        max_keepalive_connections=self.concurrent_requests,
                    ),
                    event_hooks={"request": [force_cache]},
                )
            else:
                client = httpx.AsyncClient(
                    timeout=self.timeout,
                    headers=self._base_headers,
                    follow_redirects=True,
                    limits=httpx.Limits(
                        max_connections=self.concurrent_requests,
                        max_keepalive_connections=self.concurrent_requests,
                    ),
                )
            self._client = client
            self._fetcher = HttpxFetcher(client, cookies=self._cookies)
        elif strategy == "curl_cffi":
            self._fetcher = await CurlCffiFetcher.create(headers=self._base_headers, cookies=self._cookies)
        elif strategy == "cloudscraper":
            self._fetcher = await CloudscraperFetcher.create(headers=self._base_headers, cookies=self._cookies)
        elif strategy == "playwright":
            # Playwright gets a minimal header set to mirror manual browsing (jj.py)
            self._fetcher = await PlaywrightFetcher.create(
                headers={"User-Agent": self.user_agent},
                cookies=self._cookies,
                headless=False,
                wait_after_goto_ms=self._playwright_wait_ms,
                interactive=self._playwright_interactive,
                cache_dir=self.cache_dir,
                cache_enabled=self.cache,
            )
        else:
            raise ValueError(f"Unknown fetch strategy: {strategy}")

        self._concurrency_sem = asyncio.Semaphore(self.concurrent_requests)
        return self

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        if self._fetcher:
            await self._fetcher.close()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("Crawler must be used as async context manager")
        return self._client

    @abstractmethod
    async def crawl(self, start_url: str) -> tuple[CrawlSession, list[DiscoveryRecord]]:
        pass

    def set_rate_limit(self, delay: float) -> None:
        self._effective_delay = max(0.0, delay)
        self._rate_limiter = (
            AsyncLimiter(1, self._effective_delay) if self._effective_delay > 0 else None
        )

    async def _request(self, method: str, url: str, **kwargs: Any) -> FetchResponse:
        if self._fetcher is None or self._concurrency_sem is None:
            raise RuntimeError("Crawler must be used as async context manager")
        limiter = self._rate_limiter
        semaphore = self._concurrency_sem
        headers = {**self._base_headers, **kwargs.pop("headers", {})}
        kwargs["headers"] = headers
        if self._cookies and "cookies" not in kwargs:
            kwargs["cookies"] = self._cookies
        if limiter:
            async with limiter:
                async with semaphore:
                    return await self._fetcher.request(method, url, **kwargs)
        async with semaphore:
            return await self._fetcher.request(method, url, **kwargs)

    async def get(self, url: str, **kwargs: Any) -> FetchResponse:
        return await self._request("GET", url, **kwargs)

    async def head(self, url: str, **kwargs: Any) -> FetchResponse:
        return await self._request("HEAD", url, **kwargs)

    @staticmethod
    def compute_hash(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def compute_xxhash(content: bytes) -> str:
        return xxhash.xxh64(content).hexdigest()

    @staticmethod
    def is_data_file_url(url: str, file_types: list[FileType] | None = None) -> FileType | None:
        # Try extension first
        path = urlparse(url).path.lower()
        if "." in path:
            ext = "." + path.rsplit(".", 1)[-1]
            file_type = FileType.from_extension(ext)
            if file_type != FileType.UNKNOWN:
                if file_types and file_type not in file_types:
                    return None
                return file_type
        # Try URL pattern matching (e.g., ExportReport?, XmlDataReport?)
        file_type = FileType.from_url_pattern(url)
        if file_type != FileType.UNKNOWN:
            if file_types and file_type not in file_types:
                return None
            return file_type
        return None

    async def head_check_file_type(
        self, url: str, file_types: list[FileType] | None = None
    ) -> FileType | None:
        try:
            response = await self.head(url, follow_redirects=True)
            if response.status_code != 200:
                return None
            content_type = response.headers.get("content-type", "")
            file_type = FileType.from_mime_type(content_type)
            if file_type == FileType.UNKNOWN:
                return None
            if file_types and file_type not in file_types:
                return None
            return file_type
        except Exception:
            return None

    @staticmethod
    def normalize_url(base_url: str, href: str) -> str:
        return urljoin(base_url, href)

    @staticmethod
    def same_domain(url1: str, url2: str) -> bool:
        return urlparse(url1).netloc == urlparse(url2).netloc

    @staticmethod
    def looks_like_download_link(link_text: str, has_download_attr: bool) -> bool:
        if has_download_attr:
            return True
        if not link_text:
            return False
        return any(kw in link_text.lower() for kw in BaseCrawler.DOWNLOAD_KEYWORDS)

    async def get_sitemap_urls(self, base_url: str) -> list[str]:
        parsed = urlparse(base_url)
        root = f"{parsed.scheme}://{parsed.netloc}"
        sitemap_urls: list[str] = []
        try:
            response = await self.get(f"{root}/robots.txt")
            if response.status_code == 200:
                for line in response.text.split("\n"):
                    if line.lower().startswith("sitemap:"):
                        sitemap_urls.append(line.split(":", 1)[1].strip())
        except Exception:
            pass
        default = f"{root}/sitemap.xml"
        if default not in sitemap_urls:
            sitemap_urls.append(default)
        return sitemap_urls

    async def parse_sitemap(self, sitemap_url: str) -> list[str]:
        urls: list[str] = []
        try:
            response = await self.get(sitemap_url)
            if response.status_code != 200:
                return urls
            content = response.text
            if "<sitemapindex" in content:
                for match in re.finditer(r"<loc>([^<]+)</loc>", content):
                    urls.extend(await self.parse_sitemap(match.group(1)))
            else:
                for match in re.finditer(r"<loc>([^<]+)</loc>", content):
                    urls.append(match.group(1))
        except Exception:
            pass
        return urls

    async def get_crawl_delay(self, base_url: str) -> float | None:
        parsed = urlparse(base_url)
        root = f"{parsed.scheme}://{parsed.netloc}"
        if root in self._robots_cache:
            return self._robots_cache[root]
        try:
            response = await self.get(f"{root}/robots.txt")
            if response.status_code != 200:
                self._robots_cache[root] = None
                return None
            delay = self._parse_crawl_delay(response.text)
            self._robots_cache[root] = delay
            return delay
        except Exception:
            self._robots_cache[root] = None
            return None

    def _parse_crawl_delay(self, robots_text: str) -> float | None:
        ua = self.user_agent.lower()
        current_agents: list[str] = []
        wildcard_delay: float | None = None
        matched_delay: float | None = None
        for raw in robots_text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.lower().startswith("user-agent:"):
                agent = line.split(":", 1)[1].strip().lower()
                current_agents = [agent]
            elif line.lower().startswith("crawl-delay:"):
                try:
                    delay = float(line.split(":", 1)[1].strip())
                except ValueError:
                    continue
                if "*" in current_agents:
                    wildcard_delay = delay
                elif any(agent in ua for agent in current_agents):
                    matched_delay = delay
        return matched_delay if matched_delay is not None else wildcard_delay
