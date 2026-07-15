"""Tests for models."""

from lineage_scraper.models import FileType


def test_file_type_from_extension():
    assert FileType.from_extension(".csv") == FileType.CSV
    assert FileType.from_extension(".xlsx") == FileType.EXCEL
    assert FileType.from_extension(".json") == FileType.JSON
    assert FileType.from_extension(".pdf") == FileType.PDF
    assert FileType.from_extension(".unknown") == FileType.UNKNOWN


def test_file_type_from_mime():
    assert FileType.from_mime_type("text/csv") == FileType.CSV
    assert FileType.from_mime_type("application/json") == FileType.JSON
    assert FileType.from_mime_type("application/pdf") == FileType.PDF
    assert FileType.from_mime_type("text/html") == FileType.UNKNOWN
