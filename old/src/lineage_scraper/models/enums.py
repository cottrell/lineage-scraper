"""Enumeration types for lineage scraper."""

import re
from enum import Enum


class FileType(str, Enum):
    """Recognized data file types."""

    CSV = "csv"
    EXCEL = "excel"
    JSON = "json"
    JSONL = "jsonl"
    PARQUET = "parquet"
    XML = "xml"
    SQLITE = "sqlite"
    TSV = "tsv"
    YAML = "yaml"
    PDF = "pdf"
    UNKNOWN = "unknown"

    @classmethod
    def from_extension(cls, ext: str) -> "FileType":
        """Map file extension to FileType."""
        mapping = {
            ".csv": cls.CSV,
            ".tsv": cls.TSV,
            ".xls": cls.EXCEL,
            ".xlsx": cls.EXCEL,
            ".xlsm": cls.EXCEL,
            ".json": cls.JSON,
            ".jsonl": cls.JSONL,
            ".ndjson": cls.JSONL,
            ".parquet": cls.PARQUET,
            ".pq": cls.PARQUET,
            ".xml": cls.XML,
            ".sqlite": cls.SQLITE,
            ".sqlite3": cls.SQLITE,
            ".db": cls.SQLITE,
            ".yaml": cls.YAML,
            ".yml": cls.YAML,
            ".pdf": cls.PDF,
        }
        return mapping.get(ext.lower(), cls.UNKNOWN)

    @classmethod
    def from_mime_type(cls, mime: str) -> "FileType":
        """Map MIME type to FileType."""
        mapping = {
            "text/csv": cls.CSV,
            "text/tab-separated-values": cls.TSV,
            "application/vnd.ms-excel": cls.EXCEL,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": cls.EXCEL,
            "application/json": cls.JSON,
            "application/x-ndjson": cls.JSONL,
            "application/parquet": cls.PARQUET,
            "application/xml": cls.XML,
            "text/xml": cls.XML,
            "application/x-sqlite3": cls.SQLITE,
            "application/x-yaml": cls.YAML,
            "text/yaml": cls.YAML,
            "application/pdf": cls.PDF,
        }
        return mapping.get(mime.lower().split(";")[0].strip(), cls.UNKNOWN)

    @classmethod
    def from_url_pattern(cls, url: str) -> "FileType":
        """Detect file type from URL patterns (e.g., DMO report endpoints)."""
        url_lower = url.lower()
        patterns = [
            (r"exportreport\?", cls.CSV),
            (r"xmldatareport\?", cls.XML),
            (r"pdfdatareport\?", cls.PDF),
            (r"dataexport\?", cls.CSV),
            (r"\.csv($|\?)", cls.CSV),
            (r"\.json($|\?)", cls.JSON),
            (r"\.xml($|\?)", cls.XML),
            (r"\.xlsx?($|\?)", cls.EXCEL),
            (r"\.pdf($|\?)", cls.PDF),
        ]
        for pattern, file_type in patterns:
            if re.search(pattern, url_lower):
                return file_type
        return cls.UNKNOWN


class CrawlStatus(str, Enum):
    """Status of a crawl operation."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"  # Some files failed but others succeeded
