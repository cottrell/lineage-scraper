"""Command-line interface for lineage-scraper."""

import asyncio
import csv
import io
import json

import argh
from rich.console import Console
from rich.table import Table

from .crawler import DataFileCrawler
from .models import FileType
from .storage import DiscoveryDatabase

console = Console()
FETCH_STRATEGIES = ("httpx", "curl_cffi", "cloudscraper", "playwright")


@argh.arg("-v", "--verbose", help="Show each URL as it's crawled")
@argh.arg("--fetch-strategy", choices=FETCH_STRATEGIES, help="HTTP fetcher backend")
@argh.arg("--types", help="Comma-separated file types (e.g., csv,json,parquet)")
@argh.arg("--rate-limit", help="Seconds between requests (respects crawl-delay)")
@argh.arg("--concurrent", help="Max concurrent requests")
@argh.arg("--headers-file", help="Path to JSON with extra headers to merge")
@argh.arg("--cookies-file", help="Path to JSON with cookies dict")
@argh.arg("--playwright-wait-ms", help="Extra wait after page load when using playwright (ms)")
@argh.arg("--dump-html", help="Save fetched HTML pages to cache_dir/raw_pages for debugging")
@argh.arg(
    "--playwright-interactive",
    help="Pause after page load so you can click consent; press Enter to continue",
)
def crawl(
    url: str,
    depth: int = 3,
    output: str = "lineage_data",
    follow_external: bool = False,
    download: bool = False,
    sniff: bool = False,
    sitemap: bool = False,
    no_cache: bool = False,
    refresh: bool = False,
    rate_limit: float = 0.5,
    concurrent: int = 1,
    fetch_strategy: str = "httpx",
    headers_file: str | None = None,
    cookies_file: str | None = None,
    playwright_wait_ms: int = 5000,
    dump_html: bool = False,
    playwright_interactive: bool = False,
    types: str = "csv,excel,json,jsonl,parquet,xml,sqlite,tsv,yaml,pdf",
    verbose: bool = False,
) -> None:
    """Crawl a website to discover data file URLs."""
    file_types = [FileType(t.strip()) for t in types.split(",") if t.strip()]
    use_cache = not no_cache
    extra_headers: dict[str, str] = {}
    cookies: dict[str, str] = {}
    if headers_file:
        try:
            with open(headers_file, "r", encoding="utf-8") as f:
                extra_headers = json.load(f)
        except FileNotFoundError:
            console.print(f"[red]Headers file not found:[/red] {headers_file}")
            return
    if cookies_file:
        try:
            with open(cookies_file, "r", encoding="utf-8") as f:
                cookies = json.load(f)
        except FileNotFoundError:
            console.print(f"[red]Cookies file not found:[/red] {cookies_file}")
            return

    async def _crawl() -> None:
        db = DiscoveryDatabase(output)

        console.print(f"[bold]Crawling {url}[/bold]")
        console.print(f"  Max depth: {depth}")
        console.print(f"  Download files: {download}")
        console.print(f"  Content-Type sniffing: {sniff}")
        console.print(f"  HTTP caching: {use_cache}{' (refresh)' if refresh else ''}")
        console.print(f"  Rate limit: {rate_limit}s between requests")
        console.print(f"  Concurrency: {concurrent}")
        console.print(f"  Fetch strategy: {fetch_strategy}")
        if fetch_strategy == "playwright" and playwright_interactive:
            console.print("  Playwright: interactive mode (will wait for Enter)")
        if extra_headers:
            console.print(f"  Extra headers: {list(extra_headers.keys())}")
        if cookies:
            console.print("  Cookies: provided")
        if file_types:
            console.print(f"  File types: {[ft.value for ft in file_types]}")
        console.print()

        def on_event(event: str, data: str) -> None:
            if verbose:
                if event == "page":
                    console.print(f"[dim]GET {data}[/dim]")
                elif event == "file":
                    console.print(f"[green]FOUND {data}[/green]")
                elif event == "error":
                    console.print(f"[red]ERR {data}[/red]")
                elif event == "info":
                    console.print(f"[blue]{data}[/blue]")

        async with DataFileCrawler(
            file_types=file_types,
            max_depth=depth,
            follow_external=follow_external,
            download=download,
            sniff_content_type=sniff,
            use_sitemap=sitemap,
            cache=use_cache,
            cache_refresh=refresh,
            delay=rate_limit,
            concurrent_requests=concurrent,
            fetch_strategy=fetch_strategy,
            extra_headers=extra_headers,
            cookies=cookies,
            playwright_wait_ms=playwright_wait_ms,
            playwright_interactive=playwright_interactive,
            dump_html=dump_html,
            on_event=on_event,
        ) as crawler:
            session, records = await crawler.crawl(url)

        db.save_session(session)
        for record in records:
            db.save_record(record)

        console.print("\n[bold green]Crawl complete![/bold green]")
        console.print(f"  Session ID: {session.id}")
        console.print(f"  Pages crawled: {session.pages_crawled}")
        console.print(f"  Data files found: {session.files_found}")

        if session.errors:
            console.print(f"  Errors: {len(session.errors)}")

        if records:
            console.print("\n[bold]Discovered files:[/bold]")
            for r in records[:10]:
                console.print(f"  [{r.file_type.value}] {r.url}")
            if len(records) > 10:
                console.print(f"  ... and {len(records) - 10} more")

    asyncio.run(_crawl())


def stats(data_dir: str = "lineage_data") -> None:
    """Show database statistics."""
    db = DiscoveryDatabase(data_dir)
    s = db.stats()

    console.print("[bold]Discovery Database Statistics[/bold]\n")
    console.print(f"Total records: {s['total_records']}")
    console.print(f"Total sessions: {s['total_sessions']}")

    if s["file_types"]:
        console.print("\nFile types:")
        for ft, count in sorted(s["file_types"].items(), key=lambda x: -x[1]):
            console.print(f"  {ft}: {count}")

    if s["domains"]:
        console.print("\nDomains:")
        for domain, count in sorted(s["domains"].items(), key=lambda x: -x[1])[:10]:
            console.print(f"  {domain}: {count}")


def list_records(data_dir: str = "lineage_data", file_type: str = "") -> None:
    """List all discovered data file URLs."""
    db = DiscoveryDatabase(data_dir)

    table = Table(title="Discovered Data Files")
    table.add_column("ID", style="cyan")
    table.add_column("Type")
    table.add_column("URL", max_width=60)
    table.add_column("Link Text", max_width=30)

    for record in db.list_records():
        if file_type and record.file_type.value != file_type:
            continue

        table.add_row(
            record.id,
            record.file_type.value,
            str(record.url)[:60],
            (record.provenance.link_text or "")[:30],
        )

    console.print(table)


def show(record_id: str, data_dir: str = "lineage_data") -> None:
    """Show details of a discovery record."""
    db = DiscoveryDatabase(data_dir)
    record = db.get_record(record_id)

    if not record:
        console.print(f"[red]Record not found: {record_id}[/red]")
        return

    console.print(f"[bold]Record: {record.id}[/bold]\n")
    console.print(f"[bold]URL:[/bold] {record.url}")
    console.print(f"[bold]Type:[/bold] {record.file_type.value}")

    console.print("\n[bold]Provenance:[/bold]")
    console.print(f"  Discovered from: {record.provenance.discovered_from}")
    console.print(f"  Crawl timestamp: {record.provenance.crawl_timestamp}")
    console.print(f"  Session ID: {record.provenance.crawl_session_id}")

    if record.provenance.link_text:
        console.print(f"  Link text: {record.provenance.link_text}")
    if record.provenance.link_context:
        console.print(f"  Link context: {record.provenance.link_context[:100]}...")

    if record.download_info:
        console.print("\n[bold]Download Info:[/bold]")
        console.print(f"  Size: {record.download_info.file_size} bytes")
        console.print(f"  Hash: {record.download_info.content_hash}")
        console.print(f"  MIME: {record.download_info.mime_type}")


def export(data_dir: str = "lineage_data", fmt: str = "json") -> None:
    """Export discovered URLs to JSON or CSV."""
    db = DiscoveryDatabase(data_dir)
    records = list(db.list_records())

    if fmt == "json":
        output = [
            {
                "url": str(r.url),
                "file_type": r.file_type.value,
                "discovered_from": str(r.provenance.discovered_from),
                "link_text": r.provenance.link_text,
                "crawl_timestamp": r.provenance.crawl_timestamp.isoformat(),
            }
            for r in records
        ]
        console.print(json.dumps(output, indent=2))
    else:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["url", "file_type", "discovered_from", "link_text"])
        for r in records:
            writer.writerow([
                r.url, r.file_type.value, r.provenance.discovered_from,
                r.provenance.link_text or ""
            ])
        console.print(buf.getvalue().rstrip())


@argh.arg("--url", help="Page to open for cookie capture")
@argh.arg("--output", help="Where to write cookies JSON")
def capture_cookies(
    url: str = "https://www.dmo.gov.uk/data", output: str = "cookies.json"
) -> None:
    """Open a browser so you can accept cookies, then save them for reuse."""
    async def _run() -> None:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            console.print(
                "[red]Playwright not installed.[/red] Install with "
                "`uv sync --extra playwright` and run `playwright install chromium`."
            )
            return

        console.print(f"[bold]Opening browser for {url}[/bold]")
        console.print("Click any consent, then return here and press Enter to save cookies.")

        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(url)

        await asyncio.to_thread(input, "Press Enter after accepting cookies in the browser...")

        cookies = await context.cookies()
        cookie_map = {c["name"]: c["value"] for c in cookies}
        with open(output, "w", encoding="utf-8") as f:
            json.dump(cookie_map, f, indent=2)

        console.print(f"[green]Saved cookies to {output}[/green]")

        await context.close()
        await browser.close()
        await playwright.stop()

    asyncio.run(_run())


def main() -> None:
    argh.dispatch_commands([crawl, stats, list_records, show, export, capture_cookies])


if __name__ == "__main__":
    main()
