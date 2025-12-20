"""High-throughput Facebook page email extractor.

Reads a text file containing Facebook Page URLs, fetches them headlessly via Playwright,
extracts publicly visible email addresses, and persists results to CSV along with logs.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Set

try:
    from playwright.async_api import Browser, BrowserContext, TimeoutError, async_playwright
except ImportError as exc:  # pragma: no cover - surfaced early to users
    raise SystemExit(
        "Playwright not installed. Run `pip install playwright` and `playwright install chromium`."
    ) from exc

EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


@dataclass(slots=True)
class RuntimeConfig:
    input_file: Path
    output_file: Path
    log_file: Path
    concurrency: int = 4
    min_delay_seconds: float = 2.0
    max_delay_seconds: float = 4.0
    navigation_timeout_ms: int = 25_000
    text_timeout_ms: int = 10_000
    max_retries: int = 2
    retry_backoff_seconds: float = 5.0
    headless: bool = True


def read_urls(path: Path) -> List[str]:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    urls: List[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            urls.append(line)
    return urls


def read_completed_urls(output_file: Path) -> Set[str]:
    if not output_file.exists():
        return set()

    completed: Set[str] = set()
    with output_file.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("facebook_url"):
                completed.add(row["facebook_url"].strip())
    return completed


def normalize_emails(text: str) -> List[str]:
    if not text:
        return []
    matches = {match.group(0).lower() for match in EMAIL_PATTERN.finditer(text)}
    return sorted(matches)


async def extract_text(context: BrowserContext, url: str, cfg: RuntimeConfig) -> str:
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="networkidle", timeout=cfg.navigation_timeout_ms)
        body_text = await page.inner_text("body", timeout=cfg.text_timeout_ms)
        return body_text
    finally:
        await page.close()


async def process_url(
    worker_id: int,
    context: BrowserContext,
    url: str,
    cfg: RuntimeConfig,
) -> tuple[str, List[str], Optional[str]]:
    last_error: Optional[str] = None
    for attempt in range(1, cfg.max_retries + 2):
        try:
            text = await extract_text(context, url, cfg)
            emails = normalize_emails(text)
            return url, emails, None
        except TimeoutError as exc:
            last_error = f"timeout ({exc})"
        except Exception as exc:  # pragma: no cover - defensive logging
            last_error = f"{type(exc).__name__}: {exc}"
        if attempt <= cfg.max_retries:
            await asyncio.sleep(cfg.retry_backoff_seconds)
    return url, [], last_error or "unknown error"


def ensure_csv_header(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["facebook_url", "emails", "email_count"])


async def append_csv_row(path: Path, row: Sequence[str], lock: asyncio.Lock) -> None:
    async with lock:
        with path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(row)


async def append_log(path: Path, message: str, lock: asyncio.Lock) -> None:
    async with lock:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(message + "\n")


async def worker(
    worker_id: int,
    browser: Browser,
    queue: "asyncio.Queue[str]",
    cfg: RuntimeConfig,
    csv_lock: asyncio.Lock,
    log_lock: asyncio.Lock,
    output_file: Path,
    log_file: Path,
) -> None:
    context = await browser.new_context()
    rng = random.Random(worker_id)
    try:
        while True:
            url = await queue.get()
            try:
                result_url, emails, error = await process_url(worker_id, context, url, cfg)
                csv_row = [result_url, ";".join(emails), str(len(emails))]
                await append_csv_row(output_file, csv_row, csv_lock)
                if error:
                    await append_log(
                        log_file,
                        f"worker={worker_id} url={result_url} status=error detail={error}",
                        log_lock,
                    )
                else:
                    await append_log(
                        log_file,
                        f"worker={worker_id} url={result_url} status=ok emails={len(emails)}",
                        log_lock,
                    )
            finally:
                queue.task_done()
                await asyncio.sleep(rng.uniform(cfg.min_delay_seconds, cfg.max_delay_seconds))
    except asyncio.CancelledError:  # graceful shutdown
        pass
    finally:
        await context.close()


async def run_extraction(cfg: RuntimeConfig) -> None:
    target_urls = read_urls(cfg.input_file)
    completed = read_completed_urls(cfg.output_file)
    pending_urls = [u for u in target_urls if u not in completed]

    if not pending_urls:
        print("All URLs already processed. Nothing to do.")
        return

    ensure_csv_header(cfg.output_file)
    cfg.log_file.parent.mkdir(parents=True, exist_ok=True)

    queue: asyncio.Queue[str] = asyncio.Queue()
    for url in pending_urls:
        queue.put_nowait(url)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=cfg.headless)
        csv_lock = asyncio.Lock()
        log_lock = asyncio.Lock()
        workers = [
            asyncio.create_task(
                worker(i, browser, queue, cfg, csv_lock, log_lock, cfg.output_file, cfg.log_file)
            )
            for i in range(cfg.concurrency)
        ]
        await queue.join()
        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)
        await browser.close()


def parse_args(argv: Optional[Sequence[str]] = None) -> RuntimeConfig:
    parser = argparse.ArgumentParser(description="Bulk Facebook email extractor")
    parser.add_argument("--input", type=Path, default=Path("input_urls.txt"), help="Path to URL list")
    parser.add_argument(
        "--output", type=Path, default=Path("results.csv"), help="CSV output path"
    )
    parser.add_argument("--log", type=Path, default=Path("logs.txt"), help="Log file path")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="Number of concurrent headless pages (recommended <=5 to reduce throttling)",
    )
    parser.add_argument(
        "--min-delay",
        type=float,
        default=2.0,
        help="Min delay (seconds) between requests per worker",
    )
    parser.add_argument(
        "--max-delay",
        type=float,
        default=4.0,
        help="Max delay (seconds) between requests per worker",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="Number of retry attempts after the initial try",
    )
    parser.add_argument(
        "--headful",
        action="store_true",
        help="Run Chromium in headful mode for debugging",
    )
    args = parser.parse_args(argv)

    if args.min_delay > args.max_delay:
        parser.error("--min-delay must be <= --max-delay")
    if args.concurrency < 1:
        parser.error("--concurrency must be >= 1")

    return RuntimeConfig(
        input_file=args.input,
        output_file=args.output,
        log_file=args.log,
        concurrency=args.concurrency,
        min_delay_seconds=args.min_delay,
        max_delay_seconds=args.max_delay,
        max_retries=args.retries,
        headless=not args.headful,
    )


def main(argv: Optional[Sequence[str]] = None) -> None:
    cfg = parse_args(argv)
    try:
        asyncio.run(run_extraction(cfg))
    except KeyboardInterrupt:
        print("Interrupted by user.")


if __name__ == "__main__":
    main(sys.argv[1:])
