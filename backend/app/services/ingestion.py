import asyncio
import ipaddress
import re
import socket
from collections import deque
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
from uuid import UUID

import httpx
import structlog
from bs4 import BeautifulSoup

from app.clients.ollama import ollama_client
from app.db import sources as sources_db

logger = structlog.get_logger()

MAX_PAGES = 50
CHUNK_SIZE = 2000  # ~500 tokens at ~4 chars/token
CHUNK_OVERLAP = 200  # ~50 tokens
CRAWL_DELAY = 0.15  # seconds between requests

_USER_AGENT = "Mozilla/5.0 (compatible; developer-docs-chatbot/1.0)"


@dataclass
class ScrapedPage:
    url: str
    title: str
    content: str


class TextChunker:
    def __init__(
        self,
        chunk_size: int = CHUNK_SIZE,
        chunk_overlap: int = CHUNK_OVERLAP,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(self, text: str) -> list[str]:
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if not text:
            return []
        if len(text) <= self.chunk_size:
            return [text]

        chunks: list[str] = []
        start = 0

        while start < len(text):
            end = min(start + self.chunk_size, len(text))

            if end < len(text):
                end = self._find_break(text, start, end)

            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            next_start = end - self.chunk_overlap
            start = next_start if next_start > start else start + 1

        return chunks

    def _find_break(self, text: str, start: int, end: int) -> int:
        mid = start + (self.chunk_size // 2)

        for sep in ("\n\n", "\n", ". ", " "):
            pos = text.rfind(sep, mid, end)
            if pos > mid:
                return pos + len(sep)

        return end


class PageScraper:
    def __init__(self, timeout: float = 10.0) -> None:
        self._timeout = timeout

    async def scrape_page(self, url: str, client: httpx.AsyncClient) -> ScrapedPage | None:
        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning("page_fetch_failed", url=url, error=str(e))
            return None

        return self._parse(url, response.text)

    def _parse(self, url: str, html: str) -> ScrapedPage | None:
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "aside", "header"]):
            tag.decompose()

        title = ""
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)
        elif soup.title:
            title = soup.title.get_text(strip=True)

        main = (
            soup.find("main")
            or soup.find("article")
            or soup.find(id="content")
            or soup.find(class_="content")
            or soup.body
        )
        if not main:
            return None

        content = main.get_text(separator="\n", strip=True)
        content = re.sub(r"\n{3,}", "\n\n", content).strip()

        if len(content) < 100:
            return None

        return ScrapedPage(url=url, title=title, content=content)

    def extract_links(self, base_url: str, html: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        parsed_base = urlparse(base_url)
        seen: set[str] = set()
        links: list[str] = []

        for a in soup.find_all("a", href=True):
            href = str(a.get("href", ""))
            full_url = urljoin(base_url, href).split("#")[0]
            parsed = urlparse(full_url)

            if (
                parsed.scheme in ("http", "https")
                and parsed.netloc == parsed_base.netloc
                and parsed.path.startswith(parsed_base.path)
                and full_url not in seen
            ):
                seen.add(full_url)
                links.append(full_url)

        return links


class IngestionService:
    def __init__(self) -> None:
        self._scraper = PageScraper()
        self._chunker = TextChunker()

    async def ingest_source(self, source_id: UUID, base_url: str) -> None:
        log = logger.bind(source_id=str(source_id), base_url=base_url)
        await sources_db.update_source_status(source_id, "indexing")

        try:
            # Guard the initial fetch URL against DNS rebinding (redirects are guarded separately)
            if not await self._is_safe_redirect(base_url):
                raise ValueError(f"base_url resolves to a private/loopback address: {base_url}")

            pages = await self._crawl(base_url)
            log.info("crawl_complete", pages=len(pages))

            # Build all embeddings first (outside DB transaction to avoid long-held connections)
            chunk_data: list[tuple[str, str | None, str, list[float]]] = []
            for page in pages:
                for chunk_text in self._chunker.split(page.content):
                    embedding = await ollama_client.embed(chunk_text)
                    chunk_data.append((page.url, page.title, chunk_text, embedding))

            # Atomically swap old chunks for new ones — concurrent reindex can't interleave
            await sources_db.replace_chunks_for_source(source_id, chunk_data)

            total_chunks = len(chunk_data)
            await sources_db.update_source_status(source_id, "ready", chunk_count=total_chunks)
            log.info("ingestion_complete", chunks=total_chunks)

        except Exception as e:
            log.error("ingestion_failed", error=str(e))
            # Best-effort — if DB is also down the source stays in 'indexing'
            try:
                await sources_db.update_source_status(
                    source_id, "error", error_msg="Ingestion failed"
                )
            except Exception as db_err:
                log.error("ingestion_status_update_failed", error=str(db_err))

    @staticmethod
    async def _is_safe_redirect(url: str) -> bool:
        """Return False if the URL points to a private/loopback address (DNS-resolved)."""
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        if hostname in ("localhost", "0.0.0.0", ""):
            return False
        try:
            # Resolve the hostname to catch DNS rebinding attacks
            infos = await asyncio.to_thread(socket.getaddrinfo, hostname, None)
            for info in infos:
                addr = ipaddress.ip_address(info[4][0])
                if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_unspecified:
                    return False
        except (OSError, ValueError):
            return False  # unresolvable hostname → block
        return True

    async def _crawl(self, base_url: str) -> list[ScrapedPage]:
        visited: set[str] = set()
        queued: set[str] = {base_url}
        queue: deque[str] = deque([base_url])
        pages: list[ScrapedPage] = []

        async with httpx.AsyncClient(
            timeout=10.0,
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=False,
        ) as client:
            while queue and len(visited) < MAX_PAGES:
                url = queue.popleft()
                if url in visited:
                    continue
                visited.add(url)

                # Handle redirects manually to guard against SSRF via redirect chains
                current_url = url
                response: httpx.Response | None = None
                for _ in range(5):
                    try:
                        fetch = await client.get(current_url)
                    except httpx.HTTPError as e:
                        logger.warning("crawl_fetch_failed", url=current_url, error=str(e))
                        break
                    if fetch.status_code in (301, 302, 303, 307, 308):
                        location = fetch.headers.get("location", "")
                        next_url = urljoin(current_url, location).split("#")[0]
                        if not await self._is_safe_redirect(next_url):
                            logger.warning(
                                "crawl_redirect_blocked", url=current_url, target=next_url
                            )
                            break
                        current_url = next_url
                    else:
                        response = fetch
                        break

                if response is None:
                    continue

                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as e:
                    logger.warning("crawl_fetch_failed", url=current_url, error=str(e))
                    continue

                page = self._scraper._parse(current_url, response.text)
                if page:
                    pages.append(page)
                    logger.info("page_indexed", url=current_url, chars=len(page.content))

                new_links = self._scraper.extract_links(base_url, response.text)
                for link in new_links:
                    if link not in visited and link not in queued:
                        queued.add(link)
                        queue.append(link)

                await asyncio.sleep(CRAWL_DELAY)

        return pages


ingestion_service = IngestionService()
