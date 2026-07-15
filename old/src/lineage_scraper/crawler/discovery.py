"""Data file discovery crawler."""

import asyncio
import uuid
from datetime import datetime
from typing import Any, Callable
from urllib.parse import urlparse
import logging
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from ..models import (
    CrawlSession,
    CrawlStatus,
    DiscoveryRecord,
    DownloadInfo,
    FileType,
    Provenance,
)
from .base import BaseCrawler


class DataFileCrawler(BaseCrawler):
    """Crawler that discovers data file URLs with provenance tracking."""

    def __init__(
        self,
        file_types: list[FileType] | None = None,
        max_depth: int = 3,
        follow_external: bool = False,
        download: bool = False,
        sniff_content_type: bool = False,
        use_sitemap: bool = False,
        on_event: Callable[[str, str], None] | None = None,
        dump_html: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.file_types = file_types or list(FileType)
        self.max_depth = max_depth
        self.follow_external = follow_external
        self.download = download
        self.sniff_content_type = sniff_content_type
        self.use_sitemap = use_sitemap
        self.on_event = on_event or (lambda e, d: None)
        self.dump_html = dump_html

    async def crawl(self, start_url: str) -> tuple[CrawlSession, list[DiscoveryRecord]]:
        """Crawl starting from URL, discovering data file URLs.

        Returns:
            Tuple of (session, records)
        """
        # Skip robots.txt for playwright (triggers WAF on some sites)
        skip_robots = self.fetch_strategy == "playwright"
        robots_delay = await self.get_crawl_delay(start_url) if self.respect_robots and not skip_robots else None
        effective_delay = max(self.delay, robots_delay or 0.0)
        self.set_rate_limit(effective_delay)

        session_id = str(uuid.uuid4())[:8]
        session = CrawlSession(
            id=session_id,
            start_url=start_url,
            max_depth=self.max_depth,
            follow_external=self.follow_external,
            file_types=self.file_types,
            respect_robots=self.respect_robots,
            download=self.download,
            status=CrawlStatus.IN_PROGRESS,
        )

        visited: set[str] = set()
        discovered_urls: set[str] = set()  # Track unique file URLs
        enqueued: set[str] = {start_url}
        queue: asyncio.Queue[tuple[str, int, str] | None] = asyncio.Queue()
        await queue.put((start_url, 0, start_url))

        records: list[DiscoveryRecord] = []

        # Check sitemap for data file URLs first
        if self.use_sitemap:
            sitemap_urls = await self.get_sitemap_urls(start_url)
            logging.debug(f"Found {len(sitemap_urls)} sitemaps at {start_url}")
            for sitemap_url in sitemap_urls:
                for url in await self.parse_sitemap(sitemap_url):
                    file_type = self.is_data_file_url(url, self.file_types)
                    if file_type and url not in discovered_urls:
                        discovered_urls.add(url)
                        record = await self._create_record(
                            url, sitemap_url, file_type, session_id, None, None
                        )
                        records.append(record)
                        session.files_found += 1

        async def worker() -> None:
            while True:
                item = await queue.get()
                if item is None:
                    queue.task_done()
                    break
                url, depth, parent_url = item

                try:
                    if url in visited or depth > self.max_depth:
                        continue

                    visited.add(url)

                    file_type = self.is_data_file_url(url, self.file_types)
                    if file_type:
                        if url not in discovered_urls:
                            discovered_urls.add(url)
                            self.on_event("file", f"[{file_type.value}] {url}")
                            record = await self._create_record(
                                url, parent_url, file_type, session_id, None, None
                            )
                            records.append(record)
                            session.files_found += 1
                        continue

                    self.on_event("page", url)
                    response = await self.get(url)
                    if response.status_code >= 400:
                        self.on_event("error", f"{url} -> HTTP {response.status_code}")
                        session.errors.append({"url": url, "error": f"HTTP {response.status_code}"})
                        continue
                    session.pages_crawled += 1

                    content_type = response.headers.get("content-type", "")
                    if "text/html" not in content_type:
                        continue

                    if self.dump_html:
                        try:
                            raw_dir = Path(self.cache_dir) / "raw_pages"
                            raw_dir.mkdir(parents=True, exist_ok=True)
                            safe_name = f"{uuid.uuid4().hex}.html"
                            (raw_dir / safe_name).write_text(response.text, encoding="utf-8")
                            self.on_event("info", f"saved HTML {raw_dir/safe_name}")
                        except Exception as e:
                            self.on_event("error", f"save html failed: {e}")

                    soup = BeautifulSoup(response.text, "lxml")
                    links = list(soup.find_all("a", href=True))
                    if links:
                        sample = ", ".join(self.normalize_url(url, str(a["href"])) for a in links[:5])
                        self.on_event("info", f"{url} links={len(links)} sample=[{sample}]")
                    else:
                        self.on_event("info", f"{url} links=0")

                    for link in links:
                        href = str(link["href"])
                        full_url = self.normalize_url(url, href)

                        if full_url in visited or full_url in enqueued:
                            continue

                        if not self.follow_external and not self.same_domain(
                            start_url, full_url
                        ):
                            continue

                        link_text = self._get_link_text(link)
                        has_download_attr = link.has_attr("download")

                        file_type = self.is_data_file_url(full_url, self.file_types)
                        if file_type is None:
                            lower_url = full_url.lower()
                            if "xmldatareport" in lower_url:
                                file_type = FileType.XML
                            elif "pdfdatareport" in lower_url:
                                file_type = FileType.PDF
                            elif "exportreport" in lower_url or "dataexport" in lower_url:
                                file_type = FileType.CSV
                        if file_type is None:
                            should_sniff = self.sniff_content_type or self.looks_like_download_link(
                                link_text or "", has_download_attr
                            )
                            if should_sniff:
                                file_type = await self.head_check_file_type(
                                    full_url, self.file_types
                                )

                        if file_type:
                            if full_url not in discovered_urls:
                                discovered_urls.add(full_url)
                                self.on_event("file", f"[{file_type.value}] {full_url}")
                                link_context = self._get_link_context(link)
                                record = await self._create_record(
                                    full_url,
                                    url,
                                    file_type,
                                    session_id,
                                    link_text,
                                    link_context,
                                )
                                records.append(record)
                                session.files_found += 1
                        elif urlparse(full_url).scheme in ("http", "https"):
                            enqueued.add(full_url)
                            await queue.put((full_url, depth + 1, url))
                finally:
                    queue.task_done()

        async with asyncio.TaskGroup() as tg:
            for _ in range(self.concurrent_requests):
                tg.create_task(worker())
            await queue.join()
            for _ in range(self.concurrent_requests):
                await queue.put(None)

        session.end_time = datetime.utcnow()
        session.status = (
            CrawlStatus.COMPLETED if not session.errors else CrawlStatus.PARTIAL
        )
        session.records = [r.id for r in records]

        return session, records

    async def _create_record(
        self,
        url: str,
        parent_url: str,
        file_type: FileType,
        session_id: str,
        link_text: str | None,
        link_context: str | None,
    ) -> DiscoveryRecord:
        """Create a discovery record, optionally downloading the file."""
        record_id = f"{session_id}-{uuid.uuid4().hex[:8]}"

        provenance = Provenance(
            discovered_from=parent_url,
            crawl_session_id=session_id,
            link_text=link_text,
            link_context=link_context,
        )

        download_info = None
        if self.download:
            download_info = await self._download_file(url)

        return DiscoveryRecord(
            id=record_id,
            url=url,
            file_type=file_type,
            provenance=provenance,
            download_info=download_info,
        )

    async def _download_file(self, url: str) -> DownloadInfo | None:
        """Download a file and return its info."""
        response = await self.get(url)
        if response.status_code >= 400:
            return None

        content = response.content
        return DownloadInfo(
            content_hash=self.compute_hash(content),
            file_size=len(content),
            mime_type=response.headers.get("content-type"),
            http_headers=dict(response.headers),
        )

    @staticmethod
    def _get_link_text(link: Tag) -> str | None:
        """Extract text from a link element."""
        text = link.get_text(strip=True)
        return text if text else None

    @staticmethod
    def _get_link_context(link: Tag, max_len: int = 200) -> str | None:
        """Extract surrounding context for a link."""
        # Get parent's text, limited in length
        parent = link.parent
        if parent:
            text = parent.get_text(strip=True)
            if text and len(text) > len(link.get_text(strip=True)):
                return text[:max_len] if len(text) > max_len else text
        return None
