"""Core models for discovery and provenance tracking."""

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .enums import FileType, CrawlStatus


class Provenance(BaseModel):
    discovered_from: str
    crawl_timestamp: datetime = Field(default_factory=datetime.utcnow)
    crawl_session_id: str
    link_text: str | None = None
    link_context: str | None = None


class DownloadInfo(BaseModel):
    content_hash: str
    file_size: int
    mime_type: str | None = None
    local_path: Path | None = None
    http_headers: dict[str, str] = Field(default_factory=dict)


class DiscoveryRecord(BaseModel):
    id: str
    url: str
    file_type: FileType
    provenance: Provenance
    download_info: DownloadInfo | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None


class CrawlSession(BaseModel):
    id: str
    start_url: str
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: datetime | None = None
    status: CrawlStatus = CrawlStatus.PENDING
    max_depth: int = 3
    follow_external: bool = False
    file_types: list[FileType] = Field(default_factory=list)
    respect_robots: bool = True
    download: bool = False
    pages_crawled: int = 0
    files_found: int = 0
    errors: list[dict[str, Any]] = Field(default_factory=list)
    records: list[str] = Field(default_factory=list)
