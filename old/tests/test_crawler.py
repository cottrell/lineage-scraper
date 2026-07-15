"""Tests for crawler."""

from lineage_scraper.crawler.base import BaseCrawler
from lineage_scraper.models import FileType


def test_is_data_file_url():
    assert BaseCrawler.is_data_file_url("https://example.com/data.csv") == FileType.CSV
    assert BaseCrawler.is_data_file_url("https://example.com/report.pdf") == FileType.PDF
    assert BaseCrawler.is_data_file_url("https://example.com/page.html") is None
    assert BaseCrawler.is_data_file_url("https://example.com/noextension") is None


def test_is_data_file_url_with_filter():
    url = "https://example.com/data.csv"
    assert BaseCrawler.is_data_file_url(url, [FileType.CSV]) == FileType.CSV
    assert BaseCrawler.is_data_file_url(url, [FileType.JSON]) is None


def test_normalize_url():
    base = "https://example.com/data/"
    assert BaseCrawler.normalize_url(base, "file.csv") == "https://example.com/data/file.csv"
    assert BaseCrawler.normalize_url(base, "/other/file.csv") == "https://example.com/other/file.csv"
    assert BaseCrawler.normalize_url(base, "https://other.com/file.csv") == "https://other.com/file.csv"


def test_same_domain():
    assert BaseCrawler.same_domain("https://example.com/a", "https://example.com/b")
    assert not BaseCrawler.same_domain("https://example.com/a", "https://other.com/b")
