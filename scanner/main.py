"""WScaner Scanner Service — HTTP API entry point."""

import asyncio
import json
import logging
import os
import sys
import random
from http.cookies import SimpleCookie

import aiohttp
import uvicorn
from dotenv import load_dotenv
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route

from core.engine import ScannerEngine
from core.auth_helpers import (
    perform_login,
    validate_and_inject_cookies,
    test_auth_config,
    ensure_session,
    check_session_valid,
    is_login_redirect,
    is_login_page_content,
    is_sensitive_page,
    get_random_ua,
    get_realistic_headers,
    random_delay,
    detect_login_fields,
    debug_auth_login,
    compute_auth_coverage,
    interactive_login,
    recorded_flow_login,
    _PLAYWRIGHT_AVAILABLE,
)
from core.spa_crawler import crawl_spa

from core.recorder import (
    start_recording,
    stop_recording,
    get_recording_status,
    force_reset_recording,
)
from core.logging_config import setup_logging, get_log_content, get_log_files_info

load_dotenv()

# Initialize centralized logging (file + console)
logger = setup_logging()


async def health(request: Request) -> JSONResponse:
    scan_mode = os.getenv("SCAN_MODE", "local")
    return JSONResponse({
        "status": "ok",
        "service": "ziyo-scanner",
        "mode": scan_mode,
        "playwright_available": _PLAYWRIGHT_AVAILABLE,
    })


# ──────────────────────────────────────────────────────────────────────────────
# Auth Test Endpoint
# ──────────────────────────────────────────────────────────────────────────────

async def auth_test(request: Request) -> JSONResponse:
    """
    Test authentication configuration.
    Uses improved test with HTTP→Playwright fallback and protected content verification.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    domain = body.get("domain", "")
    auth_type = body.get("auth_type", "none")
    if not domain:
        return JSONResponse({"error": "domain is required"}, status_code=400)

    if auth_type not in ("form", "cookie", "interactive", "recorded"):
        return JSONResponse({"error": "auth_type must be 'form', 'cookie', 'interactive', or 'recorded'"}, status_code=400)

    result = await test_auth_config(body, domain)
    status_code = 200 if result.get("success") else 400
    return JSONResponse(result, status_code=status_code)


# ──────────────────────────────────────────────────────────────────────────────
# Authenticated Scan — re-crawl public URLs + discover private pages
# ──────────────────────────────────────────────────────────────────────────────

async def _run_authenticated_scan(
    domain: str,
    max_depth: int,
    max_pages: int,
    auth_config: dict,
    public_urls: list[dict],
    event_queue: asyncio.Queue | None = None,
) -> dict:
    """
    Production-grade authenticated crawl:

    1. Login (HTTP → Playwright fallback)
    2. Re-crawl ALL public URLs with auth session → discover new private links
    3. BFS crawl private entry points + newly discovered links
    4. Session validation during crawl — auto re-login on 401/403/redirect
    5. Deduplication: mark URLs as 'private', 'both', or skip duplicates
    6. Anti-block: random delays, UA rotation, realistic headers

    Returns:
      {
        "success": bool,
        "urls": [...],
        "auth_error": str or None,
        "method": str,
        "session_relogins": int,
        "cookies": dict,
      }
    """
    from utils.url_utils import normalize_url, is_same_domain, is_valid_url, extract_domain, is_external
    from modules.html_module import HTMLModule
    from modules.js_module import JSModule
    from collections import deque

    timeout = aiohttp.ClientTimeout(total=10)
    connector = aiohttp.TCPConnector(limit=8, ssl=False)
    ua = get_random_ua()

    result_info = {
        "success": False,
        "urls": [],
        "auth_error": None,
        "method": "none",
        "session_relogins": 0,
        "cookies": {},
    }

    # Callback to stream auth step progress during login
    async def _auth_step_cb(info: dict):
        if event_queue:
            await event_queue.put({
                "type": "auth_step_progress",
                "phase": "auth",
                "step": info.get("step", 0),
                "total": info.get("total", 0),
                "action": info.get("action", ""),
                "description": info.get("description", ""),
            })

    try:
        async with aiohttp.ClientSession(
            connector=connector, timeout=timeout,
            headers=get_realistic_headers(ua),
        ) as session:
            # ── Step 1: Login ─────────────────────────────────────────
            # Try reusing saved session cookies first
            saved_cookies = auth_config.get("saved_session_cookies", {})
            if saved_cookies:
                logger.info(f"Attempting to reuse saved session cookies for {domain}")
                for k, v in saved_cookies.items():
                    session.cookie_jar.update_cookies({k: v})

                is_valid = await check_session_valid(session, domain)
                if is_valid:
                    logger.info(f"Saved session cookies are still valid for {domain}")
                    result_info["success"] = True
                    result_info["method"] = "saved_session"
                    result_info["cookies"] = saved_cookies
                else:
                    logger.info(f"Saved session expired for {domain}, performing fresh login")
                    session.cookie_jar.clear()
                    try:
                        login_result = await asyncio.wait_for(
                            perform_login(session, auth_config, domain, on_step_progress=_auth_step_cb),
                            timeout=120,
                        )
                    except asyncio.TimeoutError:
                        result_info["auth_error"] = "Login timed out (>2 min)"
                        result_info["method"] = "timeout"
                        logger.warning(f"Login timed out for {domain}")
                        return result_info
                    if not login_result.get("success"):
                        result_info["auth_error"] = login_result.get("error", "Login failed")
                        result_info["method"] = login_result.get("method", "unknown")
                        logger.warning(f"Auth failed for {domain}: {result_info['auth_error']}")
                        return result_info
                    result_info["success"] = True
                    result_info["method"] = login_result.get("method", "http")
                    result_info["cookies"] = login_result.get("cookies", {})
            else:
                try:
                    login_result = await asyncio.wait_for(
                        perform_login(session, auth_config, domain, on_step_progress=_auth_step_cb),
                        timeout=120,
                    )
                except asyncio.TimeoutError:
                    result_info["auth_error"] = "Login timed out (>2 min)"
                    result_info["method"] = "timeout"
                    logger.warning(f"Login timed out for {domain}")
                    return result_info
                if not login_result.get("success"):
                    result_info["auth_error"] = login_result.get("error", "Login failed")
                    result_info["method"] = login_result.get("method", "unknown")
                    logger.warning(f"Auth failed for {domain}: {result_info['auth_error']}")
                    return result_info
                result_info["success"] = True
                result_info["method"] = login_result.get("method", "http")
                result_info["cookies"] = login_result.get("cookies", {})

            logger.info(f"Login succeeded for {domain} via {result_info['method']}")

            # ── Build visited set from public scan ─────────────────────
            public_url_set = set()
            for u in public_urls:
                norm = normalize_url(u.get("url", ""))
                if norm:
                    public_url_set.add(norm)

            visited = set(public_url_set)
            results = []
            queue = deque()

            html_module = HTMLModule()
            js_module = JSModule()
            max_private = min(max_pages, 300)
            relogin_count = 0
            consecutive_auth_fails = 0
            pages_fetched = 0

            # ── Step 2: Re-crawl public URLs with auth ────────────────
            # This discovers private links that are only visible when logged in
            pass  # log moved after filter

            internal_public = [u for u in public_urls if u.get("is_internal", True)]
            # Limit re-crawl to avoid long delays
            recrawl_urls = internal_public[:30]
            logger.info(f"Re-crawling {len(recrawl_urls)} of {len(public_urls)} public URLs with auth session")

            import time as _time
            recrawl_start = _time.monotonic()
            recrawl_timeout = 120  # 2 min max for re-crawl phase

            for idx, url_info in enumerate(recrawl_urls):
                if len(results) >= max_private:
                    break

                # Check re-crawl phase timeout
                elapsed = _time.monotonic() - recrawl_start
                if elapsed > recrawl_timeout:
                    logger.warning(f"Re-crawl phase timed out after {elapsed:.0f}s, moving on")
                    break

                url = url_info.get("url", "")
                if not url or not is_valid_url(url):
                    continue

                # Emit progress every 5 URLs so frontend knows we're alive
                if idx % 5 == 0 and event_queue:
                    await event_queue.put({
                        "type": "auth_recrawl_progress",
                        "current": idx + 1,
                        "total": len(recrawl_urls),
                        "message": f"Проверка авторизованных страниц: {idx + 1}/{len(recrawl_urls)}"
                    })

                try:
                    await random_delay(0.1, 0.4)
                    pages_fetched += 1
                    logger.info(f"Auth re-crawl [{idx+1}/{len(recrawl_urls)}] {url[:80]}")

                    async with session.get(url, allow_redirects=True) as resp:
                        status_code = resp.status
                        final_url = str(resp.url)
                        content_type = resp.headers.get("Content-Type", "")

                        # Session expired? → re-login
                        if status_code in (401, 403) or is_login_redirect(final_url, status_code):
                            consecutive_auth_fails += 1
                            if consecutive_auth_fails <= 2:
                                logger.info(f"Session expired during re-crawl, re-logging in...")
                                try:
                                    sess_result = await asyncio.wait_for(
                                        ensure_session(session, auth_config, domain, force_relogin=True),
                                        timeout=60,
                                    )
                                except asyncio.TimeoutError:
                                    logger.warning("Re-login timed out during re-crawl, stopping")
                                    break
                                if sess_result.get("valid"):
                                    relogin_count += 1
                                    consecutive_auth_fails = 0
                                    continue
                                else:
                                    result_info["auth_error"] = f"Re-login failed: {sess_result.get('error')}"
                                    break
                            else:
                                logger.warning("Too many consecutive auth failures, stopping re-crawl")
                                break

                        consecutive_auth_fails = 0

                        html = ""
                        if "text/html" in content_type and status_code == 200:
                            html = await resp.text(errors="replace")

                        # Extract new links from this page (authenticated view may show more)
                        if html and is_same_domain(final_url, domain):
                            new_links = []
                            try:
                                new_links.extend(html_module.extract(final_url, html, domain))
                            except Exception:
                                pass
                            try:
                                new_links.extend(js_module.extract(final_url, html, domain))
                            except Exception:
                                pass

                            for link in new_links:
                                norm_link = normalize_url(link)
                                if norm_link and norm_link not in visited and is_valid_url(norm_link):
                                    if not is_external(norm_link, domain):
                                        queue.append((norm_link, 1))
                                    else:
                                        visited.add(norm_link)
                                        results.append({
                                            "url": norm_link,
                                            "source": "html",
                                            "status_code": None,
                                            "content_type": "",
                                            "depth": 1,
                                            "is_internal": False,
                                            "external_domain": extract_domain(norm_link),
                                            "source_url": final_url,
                                            "is_private": True,
                                        })

                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.debug(f"Re-crawl error on {url}: {e}")
                    continue

            logger.info(f"Re-crawl found {len(results)} new external + {queue.qsize() if hasattr(queue, 'qsize') else len(queue)} internal to explore")

            # ── Step 3: Add private entry points ──────────────────────
            base_url = f"https://{domain}"
            private_entry_points = [
                "/admin/", "/dashboard/", "/account/", "/profile/",
                "/settings/", "/panel/", "/manage/", "/internal/",
                "/user/", "/members/", "/backend/", "/cp/",
                "/api/", "/console/", "/portal/", "/my/",
                "/staff/", "/control/", "/cms/", "/moderator/",
            ]
            for path in private_entry_points:
                url = base_url + path
                norm = normalize_url(url)
                if norm and norm not in visited:
                    queue.append((norm, 1))

            # ── Step 4: BFS crawl with session validation ─────────────
            bfs_fetched = 0
            bfs_start = _time.monotonic()
            bfs_timeout = 120  # 2 min max for BFS phase
            logger.info(f"Starting authenticated BFS crawl ({len(queue)} URLs in queue)")

            while queue and len(results) < max_private:
                # Check BFS phase timeout
                bfs_elapsed = _time.monotonic() - bfs_start
                if bfs_elapsed > bfs_timeout:
                    logger.warning(f"BFS phase timed out after {bfs_elapsed:.0f}s ({bfs_fetched} fetched, {len(results)} found)")
                    break

                url, depth = queue.popleft()
                norm_url = normalize_url(url)
                if not norm_url or norm_url in visited or depth > max_depth or not is_valid_url(norm_url):
                    continue
                visited.add(norm_url)

                try:
                    await random_delay(0.15, 0.6)
                    pages_fetched += 1
                    bfs_fetched += 1
                    logger.info(f"Auth BFS [{bfs_fetched}] depth={depth} {norm_url[:80]}")

                    # Emit BFS progress every 10 pages
                    if bfs_fetched % 10 == 0 and event_queue:
                        await event_queue.put({
                            "type": "auth_recrawl_progress",
                            "current": bfs_fetched,
                            "total": max_private,
                            "message": f"Scanning private pages: {len(results)} found"
                        })

                    # Periodic session check (every 50 pages)
                    if pages_fetched % 50 == 0:
                        try:
                            is_valid = await asyncio.wait_for(
                                check_session_valid(session, domain), timeout=15,
                            )
                        except asyncio.TimeoutError:
                            logger.warning("Session check timed out, assuming valid")
                            is_valid = True
                        if not is_valid:
                            logger.info("Periodic session check: session expired, re-logging in")
                            try:
                                sess_result = await asyncio.wait_for(
                                    ensure_session(session, auth_config, domain, force_relogin=True),
                                    timeout=60,
                                )
                            except asyncio.TimeoutError:
                                logger.warning("Re-login timed out during BFS, stopping")
                                break
                            if sess_result.get("valid"):
                                relogin_count += 1
                            else:
                                result_info["auth_error"] = f"Re-login failed: {sess_result.get('error')}"
                                break

                    async with session.get(norm_url, allow_redirects=True) as resp:
                        status_code = resp.status
                        content_type = resp.headers.get("Content-Type", "")
                        final_url = str(resp.url)

                        # Login redirect → session died → re-login
                        if is_login_redirect(final_url, status_code) or status_code in (401, 403):
                            consecutive_auth_fails += 1
                            if consecutive_auth_fails <= 2:
                                try:
                                    sess_result = await asyncio.wait_for(
                                        ensure_session(session, auth_config, domain, force_relogin=True),
                                        timeout=60,
                                    )
                                except asyncio.TimeoutError:
                                    logger.warning("Re-login timed out during BFS, stopping")
                                    break
                                if sess_result.get("valid"):
                                    relogin_count += 1
                                    consecutive_auth_fails = 0
                                    # Re-try this URL
                                    queue.appendleft((norm_url, depth))
                                    visited.discard(norm_url)
                                    continue
                            continue

                        consecutive_auth_fails = 0

                        html = ""
                        if "text/html" in content_type and status_code == 200:
                            html = await resp.text(errors="replace")
                            # Skip if this is actually a login page
                            if is_login_page_content(html):
                                continue

                        url_is_internal = is_same_domain(final_url, domain)
                        ext_domain = "" if url_is_internal else extract_domain(final_url)

                        # This URL is private (not in public scan)
                        is_private_only = norm_url not in public_url_set
                        # If URL was in public scan but now we access it authenticated,
                        # mark it as "both" (we only add if it discovered new sub-links)

                        if is_private_only:
                            results.append({
                                "url": final_url,
                                "source": "html",
                                "status_code": status_code,
                                "content_type": content_type.split(";")[0].strip(),
                                "depth": depth,
                                "is_internal": url_is_internal,
                                "external_domain": ext_domain,
                                "source_url": "",
                                "is_private": True,
                            })

                        # Extract links (private pages have unique links)
                        if html and url_is_internal:
                            new_links = []
                            try:
                                new_links.extend(html_module.extract(final_url, html, domain))
                            except Exception:
                                pass
                            try:
                                new_links.extend(js_module.extract(final_url, html, domain))
                            except Exception:
                                pass

                            for link in new_links:
                                norm_link = normalize_url(link)
                                if norm_link and norm_link not in visited and is_valid_url(norm_link):
                                    if not is_external(norm_link, domain):
                                        if depth + 1 <= max_depth:
                                            queue.append((norm_link, depth + 1))
                                    else:
                                        visited.add(norm_link)
                                        results.append({
                                            "url": norm_link,
                                            "source": "html",
                                            "status_code": None,
                                            "content_type": "",
                                            "depth": depth + 1,
                                            "is_internal": False,
                                            "external_domain": extract_domain(norm_link),
                                            "source_url": final_url,
                                            "is_private": True,
                                        })

                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.debug(f"Auth crawl error on {norm_url}: {e}")
                    continue

            result_info["urls"] = results
            result_info["session_relogins"] = relogin_count
            logger.info(
                f"Authenticated scan complete for {domain}: "
                f"{len(results)} private URLs, {relogin_count} re-logins, "
                f"{pages_fetched} pages fetched"
            )
            return result_info

    except Exception as e:
        logger.exception(f"Authenticated scan failed: {e}")
        result_info["auth_error"] = str(e)
        return result_info


# ──────────────────────────────────────────────────────────────────────────────
# Main Scan Endpoint
# ──────────────────────────────────────────────────────────────────────────────

async def scan(request: Request) -> JSONResponse:
    """
    Run a scan and return discovered URLs.
    Phase 1: Public scan (unauthenticated)
    Phase 2: Authenticated scan (if auth_config provided)
       - Re-crawl public URLs with auth → find hidden links
       - BFS crawl private entry points
       - Deduplicate results
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    domain = body.get("domain")
    if not domain:
        return JSONResponse({"error": "domain is required"}, status_code=400)

    scan_id = body.get("scan_id")
    max_depth = body.get("max_depth", 3)
    max_pages = body.get("max_pages", 500)
    auth_config = body.get("auth_config")

    logger.info(
        f"Starting scan for {domain} "
        f"(scan_id={scan_id}, depth={max_depth}, pages={max_pages}, "
        f"auth={bool(auth_config)}, playwright={_PLAYWRIGHT_AVAILABLE})"
    )

    engine = ScannerEngine(
        domain=domain,
        max_depth=max_depth,
        max_pages=max_pages,
    )

    try:
        # Phase 1: Public scan
        results = await engine.run()
        public_count = len(results)
        logger.info(f"Public scan complete for {domain}: {public_count} URLs")

        # Phase 2: Authenticated scan
        private_results = []
        auth_info = {}
        if auth_config and auth_config.get("auth_type") in ("form", "cookie"):
            logger.info(f"Starting authenticated scan for {domain}")

            auth_scan = await _run_authenticated_scan(
                domain, max_depth, max_pages, auth_config, results,
            )

            auth_info = {
                "auth_success": auth_scan.get("success", False),
                "auth_method": auth_scan.get("method", "none"),
                "auth_error": auth_scan.get("auth_error"),
                "session_relogins": auth_scan.get("session_relogins", 0),
                "session_cookies": auth_scan.get("cookies", {}),
            }

            if auth_scan.get("success"):
                private_results = auth_scan.get("urls", [])
                logger.info(f"Authenticated scan found {len(private_results)} private URLs")

                # Deduplicate: remove private URLs that are already in public results
                public_url_set = {r.get("url", "") for r in results}
                deduped = []
                for pr in private_results:
                    url = pr.get("url", "")
                    if url not in public_url_set:
                        pr["is_private"] = True
                        deduped.append(pr)
                    # If URL found in both public and private, it stays public
                    # (no duplication)

                private_results = deduped
                results.extend(private_results)
            else:
                logger.warning(f"Auth scan failed for {domain}: {auth_scan.get('auth_error')}")

        # ── Mark sensitive pages ──────────────────────────────────────
        for url_info in results:
            url_info["is_sensitive"] = is_sensitive_page(url_info.get("url", ""))

        # ── Auth coverage stats ───────────────────────────────────────
        public_only = [u for u in results if not u.get("is_private")]
        private_only = [u for u in results if u.get("is_private")]
        auth_coverage = compute_auth_coverage(public_only, private_only)

        response_data = {
            "scan_id": scan_id,
            "domain": domain,
            "total_urls": len(results),
            "public_urls": public_count,
            "private_urls": len(private_results),
            "auth_coverage": auth_coverage,
            "urls": results,
            **auth_info,
        }

        return JSONResponse(response_data)
    except Exception as e:
        logger.exception(f"Scan failed for {domain}")
        return JSONResponse({"error": str(e)}, status_code=500)


# ──────────────────────────────────────────────────────────────────────────────
# SSE Streaming Scan
# ──────────────────────────────────────────────────────────────────────────────

async def scan_stream(request: Request) -> StreamingResponse:
    """Run a scan and stream progress events via SSE, including auth phase."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    domain = body.get("domain")
    if not domain:
        return JSONResponse({"error": "domain is required"}, status_code=400)

    scan_id = body.get("scan_id")
    max_depth = body.get("max_depth", 3)
    max_pages = body.get("max_pages", 500)
    auth_config = body.get("auth_config")

    logger.info(f"Starting SSE scan for {domain} (scan_id={scan_id}, auth={bool(auth_config)})")
    logger.debug(f"Scan params: domain={domain}, scan_id={scan_id}, max_depth={max_depth}, max_pages={max_pages}")
    if auth_config:
        logger.debug(f"Auth config: type={auth_config.get('auth_type')}, "
                     f"has_username={bool(auth_config.get('username'))}, "
                     f"has_password={bool(auth_config.get('password'))}, "
                     f"has_recorded_steps={len(auth_config.get('recorded_steps', []))}, "
                     f"home_url={auth_config.get('home_url', '')}, "
                     f"login_url={auth_config.get('login_url', '')}")

    event_queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def on_event(event: dict) -> None:
        await event_queue.put(event)

    async def run_engine():
        try:
            engine = ScannerEngine(
                domain=domain,
                max_depth=max_depth,
                max_pages=max_pages,
                on_event=on_event,
            )
            # Phase 1: Public scan
            results = await engine.run()
            public_count = len(results)

            # Phase 2: Authenticated scan (if auth_config provided)
            private_results = []
            auth_info = {}

            if auth_config and auth_config.get("auth_type") in ("form", "cookie", "interactive", "recorded"):
                await event_queue.put({
                    "type": "phase_start",
                    "phase": "auth",
                })

                logger.info(f"SSE: Starting auth phase for {domain}")

                try:
                    auth_type = auth_config.get("auth_type", "")
                    use_spa = auth_type in ("recorded", "interactive")

                    logger.debug(f"Auth phase: auth_type={auth_type}, use_spa={use_spa}")

                    if use_spa:
                        # ── SPA Browser Crawler for recorded/interactive auth ──
                        logger.info(f"SSE: Using SPA browser crawler for {domain} (auth_type={auth_type})")

                        from core.auth_helpers import recorded_flow_login, interactive_login

                        # Callback to stream auth step progress to frontend
                        async def _auth_step_cb(info: dict):
                            await event_queue.put({
                                "type": "auth_step_progress",
                                "phase": "auth",
                                "step": info.get("step", 0),
                                "total": info.get("total", 0),
                                "action": info.get("action", ""),
                                "description": info.get("description", ""),
                            })

                        if auth_type == "recorded":
                            steps = auth_config.get("recorded_steps", [])
                            username = auth_config.get("username", "")
                            password = auth_config.get("password", "")
                            logger.debug(f"Recorded flow: {len(steps)} steps, username='{username[:3]}***'")
                            logger.debug(f"Recorded steps summary: {[s.get('action','?') + ' ' + (s.get('selector','') or s.get('url',''))[:50] for s in steps]}")
                            login_result = await asyncio.wait_for(
                                recorded_flow_login(steps=steps, username=username, password=password, domain=domain, on_step_progress=_auth_step_cb),
                                timeout=300,
                            )
                            logger.debug(f"Recorded flow result: success={login_result.get('success')}, "
                                        f"cookies={len(login_result.get('cookies', {}))}, "
                                        f"method={login_result.get('method')}, "
                                        f"error={login_result.get('error', 'none')}")
                        else:  # interactive
                            home_url = auth_config.get("home_url", "") or auth_config.get("login_url", "")
                            login_result = await asyncio.wait_for(
                                interactive_login(
                                    home_url=home_url,
                                    username=auth_config.get("username", ""),
                                    password=auth_config.get("password", ""),
                                    login_button_selector=auth_config.get("login_button_selector", ""),
                                    username_selector=auth_config.get("username_selector", ""),
                                    password_selector=auth_config.get("password_selector", ""),
                                    submit_selector=auth_config.get("submit_selector", ""),
                                    domain=domain,
                                    on_step_progress=_auth_step_cb,
                                ),
                                timeout=300,
                            )

                        if not login_result.get("success"):
                            raise Exception(login_result.get("error", "Login failed"))

                        login_cookies = login_result.get("cookies", {})
                        login_method = login_result.get("method", auth_type)
                        logger.info(f"SSE: Login OK ({login_method}), {len(login_cookies)} cookies -> SPA crawl")
                        logger.debug(f"Login cookies: {list(login_cookies.keys())}")

                        await event_queue.put({"type": "auth_success", "phase": "auth", "method": login_method})
                        await event_queue.put({"type": "phase_complete", "phase": "auth", "urls_found": 0})
                        await event_queue.put({"type": "phase_start", "phase": "private_scan"})

                        logger.debug(f"Starting SPA crawl: domain={domain}, max_pages={min(max_pages, 150)}, "
                                    f"max_depth={max_depth}, overall_timeout=480, "
                                    f"start_url={auth_config.get('home_url') or 'default'}")

                        spa_result = await asyncio.wait_for(
                            crawl_spa(
                                domain=domain,
                                cookies=login_cookies,
                                start_url=auth_config.get("home_url") or None,
                                max_pages=min(max_pages, 150),
                                max_depth=max_depth,
                                overall_timeout=480,
                                event_queue=event_queue,
                            ),
                            timeout=600,
                        )

                        logger.debug(f"SPA crawl result: urls={len(spa_result.get('urls', []))}, "
                                    f"api_endpoints={len(spa_result.get('api_endpoints', []))}, "
                                    f"pages_visited={spa_result.get('pages_visited')}, "
                                    f"clicks={spa_result.get('clicks_performed')}")

                        private_results = spa_result.get("urls", [])
                        public_url_set = {r.get("url", "") for r in results}
                        deduped = []
                        for pr in private_results:
                            url = pr.get("url", "")
                            if url not in public_url_set:
                                pr["is_private"] = True
                                deduped.append(pr)
                                await event_queue.put({
                                    "type": "url_found",
                                    "url": url,
                                    "source": pr.get("source", "spa"),
                                    "status_code": pr.get("status_code"),
                                    "depth": pr.get("depth", 0),
                                    "is_internal": pr.get("is_internal", True),
                                    "external_domain": pr.get("external_domain", ""),
                                    "is_private": True,
                                })

                        private_results = deduped
                        results.extend(private_results)

                        await event_queue.put({
                            "type": "phase_complete",
                            "phase": "private_scan",
                            "urls_found": len(private_results),
                        })

                        logger.info(
                            f"SSE: SPA crawl found {len(private_results)} private URLs, "
                            f"{len(spa_result.get('api_endpoints', []))} API endpoints for {domain}"
                        )

                        auth_info = {
                            "auth_success": True,
                            "auth_method": login_method,
                            "session_cookies": login_cookies,
                        }

                    else:
                        # ── HTTP Crawler for form/cookie auth (existing logic) ──
                        auth_scan = await asyncio.wait_for(
                            _run_authenticated_scan(
                                domain, max_depth, max_pages, auth_config, results,
                                event_queue=event_queue,
                            ),
                            timeout=600,
                        )

                        auth_success = auth_scan.get("success", False)
                        auth_method = auth_scan.get("method", "none")
                        auth_error = auth_scan.get("auth_error")

                        if auth_success:
                            await event_queue.put({"type": "auth_success", "phase": "auth", "method": auth_method})
                            await event_queue.put({"type": "phase_complete", "phase": "auth", "urls_found": 0})
                            await event_queue.put({"type": "phase_start", "phase": "private_scan"})

                            private_results = auth_scan.get("urls", [])
                            public_url_set = {r.get("url", "") for r in results}
                            deduped = []
                            for pr in private_results:
                                url = pr.get("url", "")
                                if url not in public_url_set:
                                    pr["is_private"] = True
                                    deduped.append(pr)
                                    await event_queue.put({
                                        "type": "url_found",
                                        "url": url,
                                        "source": pr.get("source", "html"),
                                        "status_code": pr.get("status_code"),
                                        "depth": pr.get("depth", 0),
                                        "is_internal": pr.get("is_internal", True),
                                        "external_domain": pr.get("external_domain", ""),
                                        "is_private": True,
                                    })

                            private_results = deduped
                            results.extend(private_results)

                            await event_queue.put({
                                "type": "phase_complete",
                                "phase": "private_scan",
                                "urls_found": len(private_results),
                            })

                            logger.info(f"SSE: Auth scan found {len(private_results)} private URLs for {domain}")

                            auth_info = {
                                "auth_success": True,
                                "auth_method": auth_method,
                                "session_cookies": auth_scan.get("cookies", {}),
                            }
                        else:
                            error_msg = auth_error or "Authentication failed"
                        await event_queue.put({
                            "type": "auth_error",
                            "phase": "auth",
                            "error": error_msg,
                            "method": auth_method,
                        })
                        await event_queue.put({
                            "type": "phase_error",
                            "phase": "auth",
                            "error": error_msg,
                        })
                        # Skip private scan phase
                        await event_queue.put({
                            "type": "phase_skip",
                            "phase": "private_scan",
                            "reason": f"Auth failed: {error_msg}",
                        })

                        auth_info = {
                            "auth_success": False,
                            "auth_error": error_msg,
                            "auth_method": auth_method,
                        }

                        logger.warning(f"SSE: Auth failed for {domain}: {error_msg}")

                except asyncio.TimeoutError:
                    error_msg = "Auth timed out (>10 min). Skipping auth phase."
                    logger.warning(f"SSE auth scan timed out for {domain}")
                    await event_queue.put({
                        "type": "auth_error",
                        "phase": "auth",
                        "error": error_msg,
                        "method": "timeout",
                    })
                    await event_queue.put({
                        "type": "phase_error",
                        "phase": "auth",
                        "error": error_msg,
                    })
                    await event_queue.put({
                        "type": "phase_skip",
                        "phase": "private_scan",
                        "reason": error_msg,
                    })
                    auth_info = {
                        "auth_success": False,
                        "auth_error": error_msg,
                    }

                except Exception as auth_exc:
                    error_msg = f"Auth error: {str(auth_exc)}"
                    logger.exception(f"SSE auth scan error for {domain}")
                    await event_queue.put({
                        "type": "auth_error",
                        "phase": "auth",
                        "error": error_msg,
                        "method": "unknown",
                    })
                    await event_queue.put({
                        "type": "phase_error",
                        "phase": "auth",
                        "error": error_msg,
                    })
                    await event_queue.put({
                        "type": "phase_skip",
                        "phase": "private_scan",
                        "reason": error_msg,
                    })
                    auth_info = {
                        "auth_success": False,
                        "auth_error": error_msg,
                    }

            # Mark sensitive pages
            for url_info in results:
                url_info["is_sensitive"] = is_sensitive_page(url_info.get("url", ""))

            await event_queue.put({
                "type": "results",
                "scan_id": scan_id,
                "domain": domain,
                "total_urls": len(results),
                "public_urls": public_count,
                "private_urls": len(private_results),
                "urls": results,
                **auth_info,
            })
        except Exception as e:
            await event_queue.put({"type": "scan_error", "error": str(e)})
        finally:
            await event_queue.put(None)

    async def event_generator():
        task = asyncio.create_task(run_engine())
        try:
            while True:
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    # Send SSE comment as keepalive to prevent proxy/browser timeout
                    yield ": keepalive\n\n"
                    continue
                if event is None:
                    break
                sse_data = json.dumps(event, default=str)
                yield f"data: {sse_data}\n\n"
        except asyncio.CancelledError:
            task.cancel()
            raise
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ──────────────────────────────────────────────────────────────────────────────
# Auth Field Detection Endpoint
# ──────────────────────────────────────────────────────────────────────────────

async def auth_detect_fields(request: Request) -> JSONResponse:
    """
    Probe a login page and return all form fields found.
    Helps users figure out which CSS selectors to use.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    login_url = body.get("login_url", "")
    if not login_url:
        return JSONResponse({"error": "login_url is required"}, status_code=400)

    result = await detect_login_fields(login_url)
    return JSONResponse(result)


# ──────────────────────────────────────────────────────────────────────────────
# Auth Debug Endpoint
# ──────────────────────────────────────────────────────────────────────────────

async def auth_debug(request: Request) -> JSONResponse:
    """
    Run a debug login attempt with step-by-step results.
    Returns detailed info about each step: page fetch, form detection,
    field detection, HTTP login attempt, Playwright login attempt.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    domain = body.get("domain", "")
    if not domain:
        return JSONResponse({"error": "domain is required"}, status_code=400)

    result = await debug_auth_login(body, domain)
    return JSONResponse(result)


# ──────────────────────────────────────────────────────────────────────────────
# Recorded Flow — Test Replay
# ──────────────────────────────────────────────────────────────────────────────

async def auth_recorded_replay(request: Request) -> JSONResponse:
    """
    Test a recorded login flow by replaying the steps.
    Expects JSON: { domain, recorded_steps, username, password }
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    domain = body.get("domain", "")
    recorded_steps = body.get("recorded_steps", [])
    username = body.get("username", "")
    password = body.get("password", "")

    if not recorded_steps:
        return JSONResponse({"error": "recorded_steps is required"}, status_code=400)

    result = await recorded_flow_login(
        steps=recorded_steps,
        username=username,
        password=password,
        domain=domain,
    )
    status_code = 200 if result.get("success") else 400
    return JSONResponse(result, status_code=status_code)


# ──────────────────────────────────────────────────────────────────────────────
# Interactive Login — Test
# ──────────────────────────────────────────────────────────────────────────────

async def auth_interactive_test(request: Request) -> JSONResponse:
    """
    Test an interactive login flow.
    Expects JSON: { domain, home_url, username, password, login_button_selector?, ... }
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    domain = body.get("domain", "")
    home_url = body.get("home_url", "") or body.get("login_url", "")
    username = body.get("username", "")
    password = body.get("password", "")

    if not home_url:
        return JSONResponse({"error": "home_url or login_url is required"}, status_code=400)
    if not username or not password:
        return JSONResponse({"error": "username and password are required"}, status_code=400)

    result = await interactive_login(
        home_url=home_url,
        username=username,
        password=password,
        login_button_selector=body.get("login_button_selector", ""),
        username_selector=body.get("username_selector", ""),
        password_selector=body.get("password_selector", ""),
        submit_selector=body.get("submit_selector", ""),
        domain=domain,
    )
    status_code = 200 if result.get("success") else 400
    return JSONResponse(result, status_code=status_code)


# ──────────────────────────────────────────────────────────────────────────────
# Recorder — Start / Stop / Status
# ──────────────────────────────────────────────────────────────────────────────

async def auth_record_start(request: Request) -> JSONResponse:
    """
    Start recording a login flow.
    Opens a headful browser visible via noVNC.
    Expects JSON: { domain, start_url? }
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    domain = body.get("domain", "").strip()
    if not domain:
        return JSONResponse({"error": "domain is required"}, status_code=400)

    start_url = body.get("start_url", "") or body.get("home_url", "")
    result = await start_recording(domain=domain, start_url=start_url)
    status_code = 200 if result.get("success") else 400
    return JSONResponse(result, status_code=status_code)


async def auth_record_stop(request: Request) -> JSONResponse:
    """
    Stop an active recording session and return the recorded steps.
    Expects JSON: { session_id }
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    session_id = body.get("session_id", "")
    if not session_id:
        return JSONResponse({"error": "session_id is required"}, status_code=400)

    result = await stop_recording(session_id)
    status_code = 200 if result.get("success") else 400
    return JSONResponse(result, status_code=status_code)


async def auth_record_status(request: Request) -> JSONResponse:
    """
    Get the status of the current recording session.
    Query param: ?session_id=xxx (optional)
    """
    session_id = request.query_params.get("session_id", "")
    result = await get_recording_status(session_id)
    return JSONResponse(result)


async def auth_record_reset(request: Request) -> JSONResponse:
    """Force-reset any active recording session."""
    result = await force_reset_recording()
    return JSONResponse(result)


# ──────────────────────────────────────────────────────────────────────────────
# Log Viewer Endpoints
# ──────────────────────────────────────────────────────────────────────────────

async def logs_view(request: Request) -> JSONResponse:
    """Get log entries. Query params: file=scanner|auth|scan|error, lines=500, level=DEBUG|INFO|WARNING|ERROR"""
    params = request.query_params
    log_name = params.get("file", "scanner")
    lines = min(int(params.get("lines", "500")), 5000)
    level = params.get("level", None)

    if log_name not in ("scanner", "auth", "scan", "error"):
        return JSONResponse({"error": "Invalid log file name"}, status_code=400)

    entries = get_log_content(log_name, lines=lines, level=level)
    return JSONResponse({
        "file": log_name,
        "count": len(entries),
        "entries": entries,
    })


async def logs_files(request: Request) -> JSONResponse:
    """Get list of log files with sizes."""
    files = get_log_files_info()
    return JSONResponse({"files": files})


async def logs_clear(request: Request) -> JSONResponse:
    """Clear a specific log file."""
    try:
        data = await request.json()
    except Exception:
        data = {}
    log_name = data.get("file", "scanner")
    if log_name not in ("scanner", "auth", "scan", "error"):
        return JSONResponse({"error": "Invalid log file name"}, status_code=400)

    import os as _os
    filepath = _os.path.join("/app/logs", f"{log_name}.log")
    try:
        if _os.path.exists(filepath):
            with open(filepath, "w") as f:
                f.write("")
            logger.info(f"Log file cleared: {log_name}.log")
        return JSONResponse({"status": "ok", "file": log_name})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ──────────────────────────────────────────────────────────────────────────────
# Routes & App
# ──────────────────────────────────────────────────────────────────────────────

routes = [
    Route("/health", health, methods=["GET"]),
    Route("/scan", scan, methods=["POST"]),
    Route("/scan/stream", scan_stream, methods=["POST"]),
    Route("/auth/test", auth_test, methods=["POST"]),
    Route("/auth/detect-fields", auth_detect_fields, methods=["POST"]),
    Route("/auth/debug", auth_debug, methods=["POST"]),
    Route("/auth/interactive/test", auth_interactive_test, methods=["POST"]),
    Route("/auth/recorded/test", auth_recorded_replay, methods=["POST"]),
    Route("/auth/recorded/replay", auth_recorded_replay, methods=["POST"]),
    Route("/auth/record/start", auth_record_start, methods=["POST"]),
    Route("/auth/record/stop", auth_record_stop, methods=["POST"]),
    Route("/auth/record/status", auth_record_status, methods=["GET"]),
    Route("/auth/record/reset", auth_record_reset, methods=["POST"]),
    Route("/logs", logs_view, methods=["GET"]),
    Route("/logs/files", logs_files, methods=["GET"]),
    Route("/logs/clear", logs_clear, methods=["POST"]),
]

app = Starlette(routes=routes)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


if __name__ == "__main__":
    port = int(os.getenv("SCANNER_PORT", "8001"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
