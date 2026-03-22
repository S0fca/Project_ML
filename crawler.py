import asyncio
import aiohttp
from aiohttp import ClientSession
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse
import re
import os
import time
from datetime import datetime, timezone

import json

with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

START_URLS = config["start_urls"]
ALLOWED_DOMAINS = tuple(config["allowed_domains"])

OUTPUT_FILE = "data.jsonl"
MAX_ARTICLES = 10_000

MAX_QUEUE = 50_000
WORKER_COUNT = 20

ARTICLE_REGEX = re.compile(r"A\d{6}_\d{6}")

queue: asyncio.Queue[str] = asyncio.Queue()
seen_urls: set[str] = set()
stored_urls: set[str] = set()
saved_count = 0

write_lock = asyncio.Lock()

stop_event = asyncio.Event()

def normalize(url: str) -> str:
    p = urlparse(url)
    scheme = p.scheme or "https"
    netloc = p.netloc
    path = p.path

    if path != "/" and path.endswith("/"):
        path = path[:-1]

    return urlunparse((scheme, netloc, path, "", "", ""))


def allowed(url: str) -> bool:
    p = urlparse(url)
    return p.scheme in ("http", "https") and p.netloc in ALLOWED_DOMAINS


def is_article(url: str) -> bool:
    if not ARTICLE_REGEX.search(url):
        return False

    path = urlparse(url).path.lower()

    if any(x in path for x in [
        "/foto", "/diskuse", "/wiki/", "/video", "/hry/", "/serialy/", "/premium/", "/epaper."
    ]):
        return False

    if re.search(r"\.(jpg|jpeg|png|gif|webp|svg|jfif|pdf)$", path):
        return False

    return True


def file_size() -> int:
    return os.path.getsize(OUTPUT_FILE) if os.path.exists(OUTPUT_FILE) else 0


async def save_record(record: dict) -> None:
    global saved_count
    async with write_lock:
        url = record.get("url")
        if not url or url in stored_urls:
            return

        with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        stored_urls.add(url)
        saved_count += 1

        if saved_count >= MAX_ARTICLES:
            stop_event.set()


def parse_article(url: str, soup: BeautifulSoup) -> dict | None:
    title_tag = soup.find("h1")
    if not title_tag:
        return None

    title = title_tag.get_text(strip=True)
    if not title:
        return None

    paragraphs = [p.get_text(" ", strip=True) for p in soup.select("div#art-text p")]
    content = "\n".join([p for p in paragraphs if p]).strip()

    if len(content) < 200:
        return None

    date = None
    meta_date = soup.find("meta", {"property": "article:published_time"})
    if meta_date and meta_date.get("content"):
        date = meta_date.get("content")
    else:
        time_tag = soup.find("time")
        if time_tag and time_tag.get("datetime"):
            date = time_tag.get("datetime")

    more_gallery = soup.select_one("div.more-gallery b")
    if more_gallery and more_gallery.get_text(strip=True).isdigit():
        images_count = int(more_gallery.get_text(strip=True))
    else:
        images_count = len({img.get("src") for img in soup.select("div#art-text img") if img.get("src")})

    comments_count = 0
    discussion_link = soup.select_one("a.btndsc")
    if discussion_link:
        spans = discussion_link.find_all("span")
        if spans:
            text = spans[-1].get_text(strip=True)
            m = re.search(r"(\d+)", text)
            if m:
                comments_count = int(m.group(1))

    path_parts = urlparse(url).path.split("/")
    category = path_parts[1] if len(path_parts) > 1 and path_parts[1] else None

    scraped_at = datetime.now(timezone.utc).isoformat()

    return {
        "url": url,
        "title": title,
        "date": date,
        "category": category,
        "content": content,
        "text_length": len(content),
        "images": images_count,
        "comments": comments_count,
        "scraped_at": scraped_at,
    }


async def enqueue(url: str) -> None:
    if queue.qsize() >= MAX_QUEUE:
        return

    n = normalize(url)
    if not allowed(n):
        return

    if n in seen_urls:
        return

    seen_urls.add(n)
    await queue.put(n)


async def fetch(session: ClientSession, url: str) -> None:
    if stop_event.is_set():
        return

    norm_url = normalize(url)

    try:
        async with session.get(norm_url, timeout=aiohttp.ClientTimeout(total=25)) as resp:
            if resp.status != 200:
                return

            raw = await resp.read()
            try:
                html = raw.decode("utf-8")
            except UnicodeDecodeError:
                html = raw.decode("windows-1250", errors="ignore")

            soup = BeautifulSoup(html, "html.parser")

            if is_article(norm_url) and norm_url not in stored_urls and not stop_event.is_set():
                rec = parse_article(norm_url, soup)
                if rec:
                    await save_record(rec)
                    if rec["url"] in stored_urls:
                        print(f"[+] {saved_count}/{MAX_ARTICLES} Saved article: {rec['title'][:90]}")
            for a in soup.find_all("a", href=True):
                if stop_event.is_set():
                    break

                href = a["href"].strip()
                if not href or href.startswith(("javascript:", "#", "mailto:", "tel:")):
                    continue

                joined = urljoin(norm_url, href)
                n = normalize(joined)

                if not allowed(n):
                    continue

                path = urlparse(n).path.lower()
                if (
                    "/wiki/" in path
                    or "/video/" in path
                    or path.endswith((".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".jfif"))
                ):
                    continue

                await enqueue(n)

    except asyncio.CancelledError:
        raise
    except Exception as ex:
        print(f"Exception while fetching {norm_url}: {ex}")


async def worker(session: ClientSession, worker_id: int) -> None:
    while True:
        if stop_event.is_set() and queue.empty():
            break
        try:
            url = await asyncio.wait_for(queue.get(), timeout=5)
        except asyncio.TimeoutError:
            if stop_event.is_set():
                break
            continue

        try:
            await fetch(session, url)
        finally:
            queue.task_done()

        await asyncio.sleep(0.05)


def load_stored_urls_sync() -> int:
    global saved_count

    if not os.path.exists(OUTPUT_FILE):
        saved_count = 0
        return 0

    count = 0
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                u = obj.get("url")
                if u:
                    stored_urls.add(u)
                    count += 1
            except Exception:
                continue

    saved_count = count
    if saved_count >= MAX_ARTICLES:
        stop_event.set()

    return count


async def progress_report() -> None:
    while not stop_event.is_set():
        print(
            f"STATUS: queue={queue.qsize()} | saved={saved_count}/{MAX_ARTICLES} | "
            f"seen={len(seen_urls)} | size={file_size() / 1024 / 1024:.2f} MB"
        )
        await asyncio.sleep(30)


async def main() -> None:
    existing = load_stored_urls_sync()
    print(f"Loaded {existing} saved articles from {OUTPUT_FILE}")

    for url in START_URLS:
        await enqueue(url)

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; school-ml-project/1.0; +https://example.invalid)"
    }

    cookies = {"dCMP": "mafra=1111"}

    async with aiohttp.ClientSession(headers=headers, cookies=cookies) as session:
        reporter_task = asyncio.create_task(progress_report())
        workers = [asyncio.create_task(worker(session, i)) for i in range(WORKER_COUNT)]

        await queue.join()
        stop_event.set()

        for w in workers:
            w.cancel()
        await asyncio.gather(*workers, return_exceptions=True)

        reporter_task.cancel()
        await asyncio.gather(reporter_task, return_exceptions=True)

    print(f"Done. Saved {saved_count} articles.")


if __name__ == "__main__":
    print("Crawler is running...")
    start = time.time()
    asyncio.run(main())
    print(f"Elapsed time: {time.time() - start:.1f} s")