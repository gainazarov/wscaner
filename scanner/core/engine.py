"""Scanner Engine — the core crawling pipeline with real-time event streaming."""

import asyncio
import logging
import time
from collections import deque
from typing import Any, Callable, Awaitable
from urllib.parse import urljoin, urlparse

import aiohttp

from modules.html_module import HTMLModule
from modules.js_module import JSModule
from modules.robots_module import RobotsModule
from modules.sitemap_module import SitemapModule
from modules.bruteforce_module import BruteforceModule
from utils.url_utils import normalize_url, is_same_domain, is_valid_url, extract_domain, is_external

logger = logging.getLogger("scanner.engine")

# Type for the async event callback
EventCallback = Callable[[dict[str, Any]], Awaitable[None]]


async def _noop_callback(event: dict[str, Any]) -> None:
    pass


class ScannerEngine:
    """
    Asynchronous web scanner that discovers URLs using multiple modules.
    Supports real-time progress streaming via an event callback.

    Events emitted:
      - scan_start:      {domain, max_depth, max_pages}
      - phase_start:     {phase, module}
      - phase_complete:  {phase, module, urls_found}
      - phase_error:     {phase, module, error}
      - phase_skip:      {phase, module, reason}
      - url_found:       {url, source, status_code, depth, is_internal, external_domain}
      - crawl_progress:  {visited, total, queue_size}
      - scan_complete:   {total_urls, duration, internal_count, external_count}
      - scan_error:      {error}
    """

    def __init__(
        self,
        domain: str,
        max_depth: int = 3,
        max_pages: int = 500,
        concurrency: int = 10,
        timeout: int = 15,
        on_event: EventCallback | None = None,
    ):
        self.domain = domain.strip().lower()
        self.base_url = f"https://{self.domain}"
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.concurrency = concurrency
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.on_event = on_event or _noop_callback

        self.visited: set[str] = set()
        self.results: list[dict[str, Any]] = []
        self._start_time: float = 0
        self._internal_count: int = 0
        self._external_count: int = 0

        # Initialize modules
        self.modules = [
            HTMLModule(),
            JSModule(),
            RobotsModule(),
            SitemapModule(),
            BruteforceModule(),
        ]

    async def _emit(self, event_type: str, **data: Any) -> None:
        """Emit an event to the callback."""
        try:
            await self.on_event({"type": event_type, **data})
        except Exception as e:
            logger.debug(f"Event callback error: {e}")

    def _classify_url(self, url: str) -> tuple[bool, str]:
        """Classify a URL as internal/external and extract external domain."""
        url_is_internal = not is_external(url, self.domain)
        ext_domain = ""
        if not url_is_internal:
            ext_domain = extract_domain(url)
        return url_is_internal, ext_domain

    async def run(self) -> list[dict[str, Any]]:
        """Execute the full scanning pipeline."""
        self._start_time = time.time()
        await self._emit("scan_start", domain=self.domain, max_depth=self.max_depth, max_pages=self.max_pages)
        logger.info(f"Starting scan: {self.domain} (depth={self.max_depth}, max_pages={self.max_pages})")

        connector = aiohttp.TCPConnector(limit=self.concurrency, ssl=False)
        try:
            async with aiohttp.ClientSession(
                connector=connector,
                timeout=self.timeout,
                headers={
                    "User-Agent": "WScaner/1.0 (+https://wscaner.dev)",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
            ) as session:
                # Phase 1-3: Run special modules one-by-one so we can stream progress
                await self._run_single_special_module(session, "robots", RobotsModule)
                await self._run_single_special_module(session, "sitemap", SitemapModule)
                await self._run_single_special_module(session, "bruteforce", BruteforceModule)

                # Phase 4: BFS crawling
                await self._emit("phase_start", phase="crawl", module="HTML + JS Crawler")
                await self._bfs_crawl(session)
                await self._emit("phase_complete", phase="crawl", module="HTML + JS Crawler", urls_found=len(self.results))
        except Exception as e:
            await self._emit("scan_error", error=str(e))
            raise

        duration = round(time.time() - self._start_time, 2)
        await self._emit(
            "scan_complete",
            total_urls=len(self.results),
            duration=duration,
            internal_count=self._internal_count,
            external_count=self._external_count,
        )
        logger.info(f"Scan complete: {len(self.results)} URLs discovered in {duration}s "
                    f"({self._internal_count} internal, {self._external_count} external)")
        return self.results

    async def _run_single_special_module(
        self, session: aiohttp.ClientSession, phase_name: str, module_class: type
    ):
        """Run a single special module with event tracking."""
        module = None
        for m in self.modules:
            if isinstance(m, module_class):
                module = m
                break

        if not module:
            await self._emit("phase_skip", phase=phase_name, module=phase_name, reason="Module not found")
            return

        module_name = module.__class__.__name__
        await self._emit("phase_start", phase=phase_name, module=module_name)

        try:
            results = await module.run(self.base_url, session, self.domain)
            found_count = 0
            if isinstance(results, list):
                for url_info in results:
                    url = url_info.get("url", "")
                    if url and url not in self.visited:
                        self.visited.add(url)
                        # Classify internal/external
                        url_is_internal, ext_domain = self._classify_url(url)
                        url_info["is_internal"] = url_is_internal
                        url_info["external_domain"] = ext_domain
                        if url_is_internal:
                            self._internal_count += 1
                        else:
                            self._external_count += 1
                        self.results.append(url_info)
                        found_count += 1
                        await self._emit("url_found",
                            url=url_info.get("url", ""),
                            source=url_info.get("source", phase_name),
                            status_code=url_info.get("status_code"),
                            depth=url_info.get("depth", 0),
                            is_internal=url_is_internal,
                            external_domain=ext_domain,
                        )
            await self._emit("phase_complete", phase=phase_name, module=module_name, urls_found=found_count)
        except Exception as e:
            logger.warning(f"Module {module_name} failed: {e}")
            await self._emit("phase_error", phase=phase_name, module=module_name, error=str(e))

    async def _bfs_crawl(self, session: aiohttp.ClientSession):
        """BFS crawl starting from base URL."""
        queue: deque[tuple[str, int]] = deque()
        queue.append((self.base_url, 0))

        # Also try http variant
        http_url = f"http://{self.domain}"
        queue.append((http_url, 0))

        page_modules = [
            m for m in self.modules if isinstance(m, (HTMLModule, JSModule))
        ]

        while queue and len(self.results) < self.max_pages:
            # Process batch
            batch: list[tuple[str, int]] = []
            while queue and len(batch) < self.concurrency:
                url, depth = queue.popleft()
                normalized = normalize_url(url)

                if normalized in self.visited:
                    continue
                if depth > self.max_depth:
                    continue
                if not is_valid_url(normalized):
                    continue

                self.visited.add(normalized)
                batch.append((normalized, depth))

            if not batch:
                break

            # Emit crawl progress
            await self._emit("crawl_progress",
                visited=len(self.visited),
                total=len(self.results),
                queue_size=len(queue),
            )

            # Fetch all pages in batch concurrently
            tasks = [
                self._fetch_and_extract(session, url, depth, page_modules)
                for url, depth in batch
            ]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    logger.debug(f"Fetch error: {result}")
                    continue
                if result is None:
                    continue

                url_info, new_links = result

                # Classify internal/external
                url_is_internal, ext_domain = self._classify_url(url_info["url"])
                url_info["is_internal"] = url_is_internal
                url_info["external_domain"] = ext_domain
                if url_is_internal:
                    self._internal_count += 1
                else:
                    self._external_count += 1

                # Add this URL to results
                if len(self.results) < self.max_pages:
                    self.results.append(url_info)
                    await self._emit("url_found",
                        url=url_info.get("url", ""),
                        source=url_info.get("source", "html"),
                        status_code=url_info.get("status_code"),
                        depth=url_info.get("depth", 0),
                        is_internal=url_is_internal,
                        external_domain=ext_domain,
                    )

                # Add discovered links to queue (only internal ones for crawling)
                for link in new_links:
                    normalized_link = normalize_url(link)
                    if (
                        normalized_link not in self.visited
                        and is_valid_url(normalized_link)
                        and len(self.results) < self.max_pages
                    ):
                        link_is_internal = not is_external(normalized_link, self.domain)
                        if link_is_internal:
                            new_depth = url_info["depth"] + 1
                            if new_depth <= self.max_depth:
                                queue.append((normalized_link, new_depth))
                        else:
                            # Still record external links as discovered
                            if normalized_link not in self.visited:
                                self.visited.add(normalized_link)
                                ext_dom = extract_domain(normalized_link)
                                ext_info = {
                                    "url": normalized_link,
                                    "source": url_info.get("source", "html"),
                                    "status_code": None,
                                    "content_type": "",
                                    "depth": url_info["depth"] + 1,
                                    "is_internal": False,
                                    "external_domain": ext_dom,
                                    "source_url": url_info.get("url", ""),
                                }
                                self._external_count += 1
                                if len(self.results) < self.max_pages:
                                    self.results.append(ext_info)
                                    await self._emit("url_found",
                                        url=normalized_link,
                                        source=url_info.get("source", "html"),
                                        status_code=None,
                                        depth=url_info["depth"] + 1,
                                        is_internal=False,
                                        external_domain=ext_dom,
                                        source_url=url_info.get("url", ""),
                                    )

    async def _fetch_and_extract(
        self,
        session: aiohttp.ClientSession,
        url: str,
        depth: int,
        modules: list,
    ) -> tuple[dict, list[str]] | None:
        """Fetch a URL and extract links using modules."""
        try:
            async with session.get(url, allow_redirects=True) as response:
                status_code = response.status
                content_type = response.headers.get("Content-Type", "")
                html = ""

                if "text/html" in content_type:
                    html = await response.text(errors="replace")
                elif "javascript" in content_type or "application/json" in content_type:
                    html = await response.text(errors="replace")

                url_info = {
                    "url": str(response.url),
                    "source": "html",
                    "status_code": status_code,
                    "content_type": content_type.split(";")[0].strip(),
                    "depth": depth,
                    "is_internal": is_same_domain(str(response.url), self.domain),
                    "external_domain": "",
                }

                # Extract links
                all_links: list[str] = []
                for module in modules:
                    try:
                        links = module.extract(str(response.url), html, self.domain)
                        all_links.extend(links)
                    except Exception as e:
                        logger.debug(f"Module {module.__class__.__name__} error on {url}: {e}")

                return url_info, all_links

        except asyncio.TimeoutError:
            logger.debug(f"Timeout: {url}")
            return {
                "url": url,
                "source": "html",
                "status_code": 0,
                "content_type": "",
                "depth": depth,
                "is_internal": is_same_domain(url, self.domain),
                "external_domain": "",
            }, []
        except Exception as e:
            logger.debug(f"Error fetching {url}: {e}")
            return None
