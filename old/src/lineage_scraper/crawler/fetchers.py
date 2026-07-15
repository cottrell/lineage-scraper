"""Fetcher strategies for HTTP requests."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class FetchResponse:
    status_code: int
    headers: dict[str, str]
    text: str
    content: bytes


class Fetcher(ABC):
    @abstractmethod
    async def request(self, method: str, url: str, **kwargs: Any) -> FetchResponse:
        raise NotImplementedError

    async def get(self, url: str, **kwargs: Any) -> FetchResponse:
        return await self.request("GET", url, **kwargs)

    async def head(self, url: str, **kwargs: Any) -> FetchResponse:
        return await self.request("HEAD", url, **kwargs)

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError


class HttpxFetcher(Fetcher):
    def __init__(self, client: httpx.AsyncClient, cookies: dict[str, str]):
        self.client = client
        self.cookies = cookies

    async def request(self, method: str, url: str, **kwargs: Any) -> FetchResponse:
        req_cookies = kwargs.pop("cookies", None)
        cookies = req_cookies or self.cookies or None
        resp = await self.client.request(method, url, cookies=cookies, **kwargs)
        return FetchResponse(
            status_code=resp.status_code,
            headers=dict(resp.headers),
            text=resp.text,
            content=resp.content,
        )

    async def close(self) -> None:
        await self.client.aclose()


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


class CurlCffiFetcher(Fetcher):
    def __init__(self, session: Any, cookies: dict[str, str]):
        self.session = session
        self.cookies = cookies

    @classmethod
    async def create(cls, headers: dict[str, str], cookies: dict[str, str]) -> "CurlCffiFetcher":
        try:
            from curl_cffi import requests as cffi_requests
        except ImportError as exc:
            raise RuntimeError("curl_cffi is not installed; install with the optional extra") from exc

        session: Any = cffi_requests.AsyncSession(
            headers={**DEFAULT_BROWSER_HEADERS, **headers},
            impersonate="chrome",
            timeout=30,
        )
        return cls(session, cookies)

    async def request(self, method: str, url: str, **kwargs: Any) -> FetchResponse:
        follow_redirects = kwargs.pop("follow_redirects", True)
        req_cookies = kwargs.pop("cookies", None)
        cookies = req_cookies or self.cookies or None
        resp = await self.session.request(
            method, url, allow_redirects=follow_redirects, cookies=cookies, **kwargs
        )
        return FetchResponse(
            status_code=resp.status_code,
            headers=dict(resp.headers),
            text=resp.text,
            content=resp.content,
        )

    async def close(self) -> None:
        await self.session.close()


class CloudscraperFetcher(Fetcher):
    def __init__(self, scraper: Any, base_headers: dict[str, str], cookies: dict[str, str]):
        self.scraper = scraper
        self.base_headers = base_headers
        self.cookies = cookies

    @classmethod
    async def create(cls, headers: dict[str, str], cookies: dict[str, str]) -> "CloudscraperFetcher":
        try:
            import cloudscraper
        except ImportError as exc:
            raise RuntimeError("cloudscraper is not installed; install with the optional extra") from exc

        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "desktop": True}
        )
        merged = {**DEFAULT_BROWSER_HEADERS, **headers}
        return cls(scraper, merged, cookies)

    async def request(self, method: str, url: str, **kwargs: Any) -> FetchResponse:
        follow_redirects = kwargs.pop("follow_redirects", True)
        provided_headers = kwargs.pop("headers", {})
        headers = {**self.base_headers, **provided_headers}
        req_cookies = kwargs.pop("cookies", None)
        cookies = req_cookies or self.cookies or None
        request_kwargs = kwargs.copy()

        def do_request() -> FetchResponse:
            resp = self.scraper.request(
                method,
                url,
                headers=headers,
                allow_redirects=follow_redirects,
                cookies=cookies,
                **request_kwargs,
            )
            return FetchResponse(
                status_code=resp.status_code,
                headers=dict(resp.headers),
                text=resp.text,
                content=resp.content,
            )

        return await asyncio.to_thread(do_request)

    async def close(self) -> None:
        try:
            self.scraper.close()
        except Exception:
            pass


class PlaywrightFetcher(Fetcher):
    def __init__(
        self,
        playwright: Any,
        browser: Any,
        context: Any,
        page: Any,
        wait_after_goto_ms: int,
        interactive: bool,
        cache: dict[str, FetchResponse],
        cache_enabled: bool,
        cache_file: str | None,
    ):
        self.playwright = playwright
        self.browser = browser
        self.context = context
        self.page = page
        self.wait_after_goto_ms = wait_after_goto_ms
        self.interactive = interactive
        self._prompted = False
        self.cache = cache
        self.cache_enabled = cache_enabled
        self.cache_file = cache_file

    @classmethod
    async def create(
        cls,
        headers: dict[str, str],
        cookies: dict[str, str],
        headless: bool = False,
        wait_after_goto_ms: int = 0,
        interactive: bool = False,
        cache_dir: str | None = None,
        cache_enabled: bool = True,
    ) -> "PlaywrightFetcher":
        import json
        from pathlib import Path

        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError(
                "playwright is not installed; install with the optional extra and run `playwright install chromium`"
            ) from exc

        # Simple setup like jj.py - only user_agent, no extra headers (triggers bot detection)
        ua = headers.get("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        p = await async_playwright().start()
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(user_agent=ua)
        page = await context.new_page()

        # Load cache from disk
        cache: dict[str, FetchResponse] = {}
        cache_file: str | None = None
        if cache_enabled and cache_dir:
            Path(cache_dir).mkdir(parents=True, exist_ok=True)
            cache_file = str(Path(cache_dir) / "playwright_cache.json")
            try:
                with open(cache_file, "r") as f:
                    for url, data in json.load(f).items():
                        cache[url] = FetchResponse(
                            status_code=data["status_code"],
                            headers=data["headers"],
                            text=data["text"],
                            content=data["text"].encode("utf-8"),
                        )
            except (FileNotFoundError, json.JSONDecodeError):
                pass

        return cls(p, browser, context, page, wait_after_goto_ms, interactive, cache, cache_enabled, cache_file)

    async def request(self, method: str, url: str, **kwargs: Any) -> FetchResponse:
        # Exactly like jj.py - no try/except, no timeouts
        if self.cache_enabled and method.upper() == "GET" and url in self.cache:
            return self.cache[url]

        # jj.py: page.goto(data_url)
        await self.page.goto(url)
        # jj.py: page.wait_for_load_state('networkidle')
        await self.page.wait_for_load_state("networkidle")
        # jj.py: time.sleep(5)
        if self.wait_after_goto_ms:
            await self.page.wait_for_timeout(self.wait_after_goto_ms)

        # Interactive mode - let user solve CAPTCHA/consent (once only)
        if self.interactive and not self._prompted:
            self._prompted = True
            title = await self.page.title()
            current_url = self.page.url
            print(f"\nPlaywright: loaded '{title}' at {current_url}")
            print("Solve CAPTCHA/consent if needed, then press Enter...")
            await asyncio.to_thread(input, "")
            await self.page.wait_for_load_state("networkidle")

        text = await self.page.content()
        result = FetchResponse(
            status_code=200,
            headers={"content-type": "text/html"},  # Playwright always returns HTML
            text=text,
            content=text.encode("utf-8"),
        )
        if self.cache_enabled and method.upper() == "GET":
            self.cache[url] = result
        return result

    async def close(self) -> None:
        try:
            await self.context.close()
            await self.browser.close()
            await self.playwright.stop()
        except Exception:
            pass
