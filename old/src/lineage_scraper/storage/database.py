"""JSON file-based storage for discovery records."""

from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

from ..models import DiscoveryRecord, CrawlSession


class DiscoveryDatabase:
    def __init__(self, data_dir: str | Path = "lineage_data"):
        self.data_dir = Path(data_dir)
        self.records_dir = self.data_dir / "records"
        self.sessions_dir = self.data_dir / "sessions"
        self.files_dir = self.data_dir / "files"
        self.records_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def save_record(self, record: DiscoveryRecord) -> Path:
        path = self.records_dir / f"{record.id}.json"
        path.write_text(record.model_dump_json(indent=2))
        return path

    def get_record(self, record_id: str) -> DiscoveryRecord | None:
        path = self.records_dir / f"{record_id}.json"
        if not path.exists():
            return None
        return DiscoveryRecord.model_validate_json(path.read_text())

    def save_session(self, session: CrawlSession) -> Path:
        path = self.sessions_dir / f"{session.id}.json"
        path.write_text(session.model_dump_json(indent=2))
        return path

    def get_session(self, session_id: str) -> CrawlSession | None:
        path = self.sessions_dir / f"{session_id}.json"
        if not path.exists():
            return None
        return CrawlSession.model_validate_json(path.read_text())

    def save_file(self, content: bytes, content_hash: str, extension: str) -> Path:
        self.files_dir.mkdir(exist_ok=True)
        subdir = self.files_dir / content_hash[:2]
        subdir.mkdir(exist_ok=True)
        path = subdir / f"{content_hash}.{extension}"
        path.write_bytes(content)
        return path

    def list_records(self) -> Iterator[DiscoveryRecord]:
        for path in self.records_dir.glob("*.json"):
            yield DiscoveryRecord.model_validate_json(path.read_text())

    def list_sessions(self) -> Iterator[CrawlSession]:
        for path in self.sessions_dir.glob("*.json"):
            yield CrawlSession.model_validate_json(path.read_text())

    def find_by_url(self, url: str) -> list[DiscoveryRecord]:
        return [r for r in self.list_records() if str(r.url) == url]

    def find_by_type(self, file_type: str) -> list[DiscoveryRecord]:
        return [r for r in self.list_records() if r.file_type.value == file_type]

    def stats(self) -> dict[str, Any]:
        records = list(self.list_records())
        sessions = list(self.list_sessions())
        file_types: dict[str, int] = {}
        domains: dict[str, int] = {}
        for r in records:
            ft = r.file_type.value
            file_types[ft] = file_types.get(ft, 0) + 1
            domain = urlparse(str(r.url)).netloc
            domains[domain] = domains.get(domain, 0) + 1
        return {
            "total_records": len(records),
            "total_sessions": len(sessions),
            "file_types": file_types,
            "domains": domains,
        }
