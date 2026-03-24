"""
Authenticated scanning helpers — production-grade auth module.

Features:
  - HTTP form login with full CSRF handling
  - Playwright headless browser fallback for SPA / JS-heavy sites
  - Priority-based form field detection
  - Session validation & auto re-login
  - Cookie expiration detection
  - Anti-block protection (UA rotation, random delays, realistic headers)
  - Improved auth testing
"""

import asyncio
import logging
import random
import time
from typing import Optional
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger("scanner.auth")

# ──────────────────────────────────────────────────────────────────────────────
# Anti-block: User-Agent rotation + realistic headers
# ──────────────────────────────────────────────────────────────────────────────

USER_AGENTS = [
    # Chrome 126-128 (latest as of 2025)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    # Firefox 127-128
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.5; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
    # Edge 127-128
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0",
    # Safari 17.5
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
]


def get_random_ua() -> str:
    return random.choice(USER_AGENTS)


def get_realistic_headers(ua: Optional[str] = None) -> dict:
    """Return browser-like headers to avoid bot detection."""
    return {
        "User-Agent": ua or get_random_ua(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Connection": "keep-alive",
    }


async def random_delay(min_s: float = 0.3, max_s: float = 1.5):
    """Random delay to avoid bot detection."""
    await asyncio.sleep(random.uniform(min_s, max_s))


# ──────────────────────────────────────────────────────────────────────────────
# Form field detection — priority-based
# ──────────────────────────────────────────────────────────────────────────────

# Priority order for username / email fields
_USERNAME_SELECTORS = [
    # Explicit selectors from Django, WordPress, and common CMSs
    'input[name="username"]',
    'input[name="email"]',
    'input[name="login"]',
    'input[name="user"]',
    'input[name="log"]',          # WordPress
    'input[name="user_login"]',   # WordPress
    'input[name="identification"]',
    'input[id="id_username"]',    # Django admin
    'input[id="login"]',
    'input[id="email"]',
    'input[id="username"]',
    # Type-based fallbacks
    'input[type="email"]',
    'input[type="text"]',         # last resort
]

_PASSWORD_SELECTORS = [
    'input[name="password"]',
    'input[name="pass"]',
    'input[name="pwd"]',          # WordPress
    'input[name="user_password"]',
    'input[id="id_password"]',    # Django admin
    'input[id="password"]',
    'input[type="password"]',
]

_SUBMIT_SELECTORS = [
    'button[type="submit"]',
    'input[type="submit"]',
    'button:not([type])',          # button without type defaults to submit
    '#login-btn',
    '#submit',
    '.login-button',
    '.btn-login',
    '.btn-primary',
]

_LOGIN_FAIL_INDICATORS = [
    "invalid", "incorrect", "wrong", "failed", "error",
    "неверный", "ошибка", "неправильный", "не найден",
    "unauthorized", "denied", "bad credentials",
    "try again", "попробуйте снова",
    "please enter a correct", "login failed",
]

# Sensitive page path patterns
SENSITIVE_PAGE_PATTERNS = [
    "/admin", "/settings", "/billing", "/payment",
    "/api-keys", "/tokens", "/secrets", "/credentials",
    "/users", "/roles", "/permissions", "/security",
    "/config", "/configuration", "/manage", "/moderator",
    "/staff", "/superadmin", "/root", "/console",
    "/database", "/backup", "/logs", "/audit",
    "/financial", "/invoice", "/subscription",
    "/private", "/internal", "/restricted",
    "/account/delete", "/account/close",
    "/2fa", "/mfa", "/otp",
]


def _find_field(soup: BeautifulSoup, user_selector: str, fallback_selectors: list[str], form=None) -> Optional[str]:
    """
    Find a form field name using priority-based detection.
    1. User-provided CSS selector (highest priority)
    2. Fallback selectors list
    3. Generic fallback: any visible input with matching type characteristics
    Returns the 'name' attribute of the found input, or None.
    """
    search_root = form if form else soup

    # Priority 1: user-provided selector
    if user_selector:
        tag = search_root.select_one(user_selector)
        if not tag:
            tag = soup.select_one(user_selector)
        if tag and tag.get("name"):
            return tag["name"]

    # Priority 2: fallback selectors
    for sel in fallback_selectors:
        try:
            tag = search_root.select_one(sel)
            if not tag:
                tag = soup.select_one(sel)
            if tag and tag.get("name"):
                return tag["name"]
        except Exception:
            continue

    # Priority 3: Generic detection — find ANY input that might match
    if search_root:
        all_inputs = search_root.find_all("input")
        is_password_search = any("password" in s for s in fallback_selectors)

        if is_password_search:
            # Look for any password type input
            for inp in all_inputs:
                if inp.get("type", "").lower() == "password" and inp.get("name"):
                    return inp["name"]
        else:
            # Look for text-like inputs (not hidden, not password, not submit)
            exclude_types = {"hidden", "password", "submit", "button", "checkbox", "radio", "file", "image", "reset"}
            for inp in all_inputs:
                inp_type = inp.get("type", "text").lower()
                if inp_type not in exclude_types and inp.get("name"):
                    # Check if placeholder or aria-label hints at username/email
                    placeholder = (inp.get("placeholder") or "").lower()
                    aria = (inp.get("aria-label") or "").lower()
                    label_text = f"{placeholder} {aria}"
                    if any(kw in label_text for kw in ["user", "email", "login", "логин", "почта", "имя"]):
                        return inp["name"]
            # Ultimate fallback: first non-hidden, non-password, non-submit input
            for inp in all_inputs:
                inp_type = inp.get("type", "text").lower()
                if inp_type not in exclude_types and inp.get("name"):
                    return inp["name"]

    return None


def _find_login_form(soup: BeautifulSoup) -> Optional[BeautifulSoup]:
    """
    Find the login form on a page.
    Checks for forms with password fields, action containing 'login', etc.
    """
    forms = soup.find_all("form")
    if not forms:
        return None

    # Priority 1: form that has a password field
    for form in forms:
        if form.find("input", {"type": "password"}):
            return form

    # Priority 2: form with action containing login/auth keywords
    for form in forms:
        action = (form.get("action") or "").lower()
        form_id = (form.get("id") or "").lower()
        form_class = " ".join(form.get("class", [])).lower()
        text = f"{action} {form_id} {form_class}"
        if any(kw in text for kw in ["login", "sign", "auth", "session"]):
            return form

    # Fallback: first form
    return forms[0] if forms else None


def is_sensitive_page(url: str) -> bool:
    """Check if a URL path matches sensitive page patterns."""
    from urllib.parse import urlparse
    path = urlparse(url).path.lower().rstrip("/")
    for pattern in SENSITIVE_PAGE_PATTERNS:
        if path == pattern.rstrip("/") or path.startswith(pattern):
            return True
    return False


# ──────────────────────────────────────────────────────────────────────────────
# Login field detection — probe endpoint helper
# ──────────────────────────────────────────────────────────────────────────────

async def detect_login_fields(login_url: str) -> dict:
    """
    Fetch the login page and analyze ALL form fields present.
    Returns structured data about every input field found,
    plus auto-detected candidates for username/password/submit.
    """
    result = {
        "login_url": login_url,
        "success": False,
        "fields": [],
        "forms_count": 0,
        "detected_username_field": None,
        "detected_password_field": None,
        "detected_submit": None,
        "suggested_username_selector": "",
        "suggested_password_selector": "",
        "suggested_submit_selector": "",
    }

    try:
        timeout = aiohttp.ClientTimeout(total=15)
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(
            connector=connector, timeout=timeout,
            headers=get_realistic_headers(),
        ) as session:
            async with session.get(login_url, allow_redirects=True) as resp:
                html = await resp.text(errors="replace")

        soup = BeautifulSoup(html, "lxml")
        forms = soup.find_all("form")
        result["forms_count"] = len(forms)

        form = _find_login_form(soup)
        search_root = form if form else soup

        # Enumerate ALL input fields
        all_inputs = search_root.find_all("input")
        fields = []
        for inp in all_inputs:
            inp_type = inp.get("type", "text").lower()
            if inp_type == "hidden":
                continue  # skip hidden fields in the UI listing

            field_info = {
                "tag": "input",
                "type": inp_type,
                "name": inp.get("name", ""),
                "id": inp.get("id", ""),
                "placeholder": inp.get("placeholder", ""),
                "aria_label": inp.get("aria-label", ""),
                "autocomplete": inp.get("autocomplete", ""),
                "required": inp.has_attr("required"),
                "css_selector": "",
            }
            # Build a useful CSS selector for this field
            if inp.get("id"):
                field_info["css_selector"] = f"#{inp['id']}"
            elif inp.get("name"):
                field_info["css_selector"] = f'input[name="{inp["name"]}"]'
            elif inp_type not in ("text", ""):
                field_info["css_selector"] = f'input[type="{inp_type}"]'

            fields.append(field_info)

        # Also find buttons/submits
        buttons = search_root.find_all(["button", "input"], {"type": ["submit", "button"]})
        for btn in buttons:
            btn_text = btn.get_text(strip=True) or btn.get("value", "")
            field_info = {
                "tag": btn.name,
                "type": btn.get("type", "button"),
                "name": btn.get("name", ""),
                "id": btn.get("id", ""),
                "text": btn_text,
                "css_selector": "",
            }
            if btn.get("id"):
                field_info["css_selector"] = f"#{btn['id']}"
            elif btn.get("type") == "submit":
                field_info["css_selector"] = f'{btn.name}[type="submit"]'
            fields.append(field_info)

        # Find buttons without explicit type (default to submit in forms)
        plain_buttons = search_root.find_all("button", {"type": None})
        for btn in plain_buttons:
            btn_text = btn.get_text(strip=True)
            field_info = {
                "tag": "button",
                "type": "submit (implicit)",
                "name": btn.get("name", ""),
                "id": btn.get("id", ""),
                "text": btn_text,
                "css_selector": "",
            }
            if btn.get("id"):
                field_info["css_selector"] = f"#{btn['id']}"
            else:
                field_info["css_selector"] = 'button:not([type])'
            fields.append(field_info)

        result["fields"] = fields

        # Auto-detect best candidates
        username_name = _find_field(soup, "", _USERNAME_SELECTORS, form)
        password_name = _find_field(soup, "", _PASSWORD_SELECTORS, form)

        if username_name:
            result["detected_username_field"] = username_name
            result["suggested_username_selector"] = f'input[name="{username_name}"]'
        if password_name:
            result["detected_password_field"] = password_name
            result["suggested_password_selector"] = f'input[name="{password_name}"]'

        # Detect submit
        for sel in _SUBMIT_SELECTORS:
            tag = search_root.select_one(sel) if search_root else soup.select_one(sel)
            if tag:
                if tag.get("id"):
                    result["suggested_submit_selector"] = f"#{tag['id']}"
                else:
                    result["suggested_submit_selector"] = sel
                result["detected_submit"] = tag.get_text(strip=True) or tag.get("value", sel)
                break

        result["success"] = True
        return result

    except Exception as e:
        logger.exception(f"detect_login_fields error: {e}")
        result["error"] = str(e)
        return result


# ──────────────────────────────────────────────────────────────────────────────
# HTTP Form Login (with full CSRF handling)
# ──────────────────────────────────────────────────────────────────────────────

async def http_form_login(
    session: aiohttp.ClientSession,
    login_url: str,
    username: str,
    password: str,
    username_selector: str = "",
    password_selector: str = "",
    submit_selector: str = "",
) -> dict:
    """
    Perform form-based login via HTTP POST with full CSRF handling.

    Steps:
      1. GET login page (sets CSRF cookies)
      2. Parse HTML, find login form
      3. Extract CSRF token from hidden fields
      4. Resolve username/password field names via priority detection
      5. POST form data with all hidden fields + credentials
      6. Verify success via redirect + cookies + error word detection
    """
    try:
        await random_delay(0.2, 0.8)

        # Step 1: GET login page — this sets CSRF cookies
        async with session.get(login_url, allow_redirects=True) as resp:
            html = await resp.text(errors="replace")
            page_url = str(resp.url)
            page_status = resp.status

        if page_status >= 400:
            return {"success": False, "error": f"Login page returned status {page_status}"}

        # Capture pre-login cookies (CSRF, analytics, etc.)
        pre_login_cookies = {}
        for cookie in session.cookie_jar:
            pre_login_cookies[cookie.key] = cookie.value

        soup = BeautifulSoup(html, "lxml")

        # Step 2: Find the login form
        form = _find_login_form(soup)
        form_action = login_url
        form_method = "POST"

        if form:
            action = form.get("action", "")
            if action:
                form_action = urljoin(page_url, action)
            form_method = (form.get("method") or "POST").upper()

        # Step 3: Resolve field names via priority detection
        username_field = _find_field(soup, username_selector, _USERNAME_SELECTORS, form)
        password_field = _find_field(soup, password_selector, _PASSWORD_SELECTORS, form)

        if not username_field:
            username_field = "username"
            logger.warning("Could not auto-detect username field, using 'username'")

        if not password_field:
            password_field = "password"
            logger.warning("Could not auto-detect password field, using 'password'")

        # Step 4: Gather ALL hidden fields (CSRF tokens, nonces, etc.)
        form_data = {}
        if form:
            for hidden in form.select("input[type=hidden]"):
                name = hidden.get("name")
                if name:
                    form_data[name] = hidden.get("value", "")

        # Also check meta tags for CSRF tokens (common in SPA frameworks)
        csrf_meta = soup.find("meta", {"name": "csrf-token"})
        if csrf_meta and csrf_meta.get("content"):
            # Try common CSRF field names
            for csrf_name in ["_token", "csrf_token", "csrfmiddlewaretoken", "_csrf"]:
                if csrf_name not in form_data:
                    form_data[csrf_name] = csrf_meta["content"]
                    break

        form_data[username_field] = username
        form_data[password_field] = password

        logger.info(
            f"HTTP form login: {form_method} {form_action} "
            f"user_field={username_field} pass_field={password_field} "
            f"hidden_fields={[k for k in form_data if k not in (username_field, password_field)]}"
        )

        await random_delay(0.3, 1.0)

        # Step 5: POST with CSRF cookies already in session
        post_headers = {
            "Referer": page_url,
            "Origin": f"{urlparse(page_url).scheme}://{urlparse(page_url).netloc}",
        }

        async with session.post(
            form_action, data=form_data, allow_redirects=True, headers=post_headers,
        ) as login_resp:
            login_body = await login_resp.text(errors="replace")
            final_status = login_resp.status

            cookies = {}
            for cookie in session.cookie_jar:
                cookies[cookie.key] = cookie.value

            final_url = str(login_resp.url)
            login_url_base = login_url.rstrip("/").split("?")[0]
            final_url_base = final_url.rstrip("/").split("?")[0]
            is_redirect_away = login_url_base != final_url_base
            has_session = bool(cookies)

            # Check for NEW cookies (not pre-existing CSRF/analytics)
            new_cookies = {k: v for k, v in cookies.items() if k not in pre_login_cookies}
            has_new_cookies = bool(new_cookies)

            # Check for error indicators
            body_lower = login_body.lower()
            has_error = any(w in body_lower for w in _LOGIN_FAIL_INDICATORS)

            # Check for success indicators
            has_dashboard = any(
                w in body_lower
                for w in ["dashboard", "welcome", "logout", "sign out", "my account",
                          "панель", "выйти", "профиль"]
            )

            # Check if still on login page
            still_on_login_page = (
                ('type="password"' in body_lower or "type='password'" in body_lower)
                and any(w in body_lower for w in ["sign in", "log in", "login", "войти", "авторизация", "вход"])
            )

            logger.info(
                f"Login result: status={final_status} redirect={is_redirect_away} "
                f"cookies={len(cookies)} new_cookies={len(new_cookies)} "
                f"has_error={has_error} has_dashboard={has_dashboard} "
                f"still_on_login={still_on_login_page}"
            )

            # Determine success
            if has_error:
                return {"success": False, "error": "Invalid credentials or form error detected", "method": "http"}

            if still_on_login_page and not is_redirect_away and not has_dashboard:
                return {"success": False, "error": "Still on login page after submit — credentials likely incorrect", "method": "http"}

            if has_session and (is_redirect_away or has_dashboard) and has_new_cookies:
                return {
                    "success": True,
                    "cookies": cookies,
                    "method": "http",
                    "final_url": final_url,
                }
            elif has_session and (is_redirect_away or has_dashboard):
                return {
                    "success": True,
                    "cookies": cookies,
                    "method": "http",
                    "final_url": final_url,
                    "warning": "Login may have succeeded (redirected but no new cookies detected)",
                }
            elif has_new_cookies and not has_error and final_status < 400:
                return {
                    "success": True,
                    "cookies": cookies,
                    "method": "http",
                    "final_url": final_url,
                    "warning": "Login may have succeeded (new cookies set but no redirect)",
                }
            else:
                msg = "Login failed"
                if has_error:
                    msg = "Invalid credentials or form error detected"
                elif not has_session:
                    msg = "No session cookies received after login"
                elif final_status >= 400:
                    msg = f"Login returned status {final_status}"
                return {"success": False, "error": msg, "method": "http"}

    except Exception as e:
        logger.exception(f"HTTP form login error: {e}")
        return {"success": False, "error": str(e), "method": "http"}


# ──────────────────────────────────────────────────────────────────────────────
# Playwright Headless Browser Fallback
# ──────────────────────────────────────────────────────────────────────────────

_PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.async_api import async_playwright
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    pass


async def playwright_form_login(
    login_url: str,
    username: str,
    password: str,
    username_selector: str = "",
    password_selector: str = "",
    submit_selector: str = "",
    domain: str = "",
) -> dict:
    """
    Fallback login using headless Chromium via Playwright.
    Works on SPA / React / Next.js / complex JS forms / OAuth.

    Steps:
      1. Open browser → navigate to login page
      2. Find & fill username + password fields
      3. Click submit
      4. Wait for navigation
      5. Extract cookies from browser context
    """
    if not _PLAYWRIGHT_AVAILABLE:
        return {
            "success": False,
            "error": "Playwright not installed — headless browser fallback unavailable",
            "method": "playwright",
        }

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            context = await browser.new_context(
                user_agent=get_random_ua(),
                viewport={"width": 1366, "height": 768},
                locale="en-US",
                timezone_id="America/New_York",
            )

            page = await context.new_page()

            # Remove webdriver detection
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => false });
                delete navigator.__proto__.webdriver;
            """)

            logger.info(f"Playwright: navigating to {login_url}")
            await page.goto(login_url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(1)  # Wait for JS to fully initialize

            # Capture pre-login state for comparison
            pre_login_cookies = await context.cookies()
            pre_login_cookie_names = {c["name"] for c in pre_login_cookies}
            pre_login_url = page.url
            pre_login_content = await page.content()

            # Find username field
            username_el = None
            if username_selector:
                try:
                    username_el = page.locator(username_selector).first
                    if await username_el.count() == 0:
                        username_el = None
                except Exception:
                    pass

            if not username_el:
                for sel in _USERNAME_SELECTORS:
                    try:
                        loc = page.locator(sel).first
                        if await loc.count() > 0 and await loc.is_visible():
                            username_el = loc
                            logger.info(f"Playwright: found username field via selector: {sel}")
                            break
                    except Exception:
                        continue

            # Generic fallback: find by placeholder/aria-label
            if not username_el:
                for attr_val in ["username", "email", "login", "user", "логин", "почта"]:
                    try:
                        loc = page.locator(f'input[placeholder*="{attr_val}" i]').first
                        if await loc.count() > 0 and await loc.is_visible():
                            username_el = loc
                            logger.info(f"Playwright: found username field via placeholder containing '{attr_val}'")
                            break
                    except Exception:
                        continue
                    try:
                        loc = page.locator(f'input[aria-label*="{attr_val}" i]').first
                        if await loc.count() > 0 and await loc.is_visible():
                            username_el = loc
                            logger.info(f"Playwright: found username field via aria-label containing '{attr_val}'")
                            break
                    except Exception:
                        continue

            # Ultimate fallback: first visible text/email input that's not a password
            if not username_el:
                try:
                    all_inputs = page.locator('input:visible')
                    count = await all_inputs.count()
                    for i in range(count):
                        inp = all_inputs.nth(i)
                        inp_type = (await inp.get_attribute("type") or "text").lower()
                        if inp_type in ("text", "email", "tel", ""):
                            username_el = inp
                            logger.info(f"Playwright: using first visible {inp_type} input as username field")
                            break
                except Exception:
                    pass

            if not username_el:
                # Collect all visible inputs info for debug
                debug_fields = []
                try:
                    all_inputs = page.locator('input:visible')
                    count = await all_inputs.count()
                    for i in range(min(count, 10)):
                        inp = all_inputs.nth(i)
                        debug_fields.append({
                            "type": await inp.get_attribute("type") or "text",
                            "name": await inp.get_attribute("name") or "",
                            "id": await inp.get_attribute("id") or "",
                            "placeholder": await inp.get_attribute("placeholder") or "",
                        })
                except Exception:
                    pass
                await browser.close()
                return {
                    "success": False,
                    "error": f"Could not find username field. Found {len(debug_fields)} visible input(s): {debug_fields}. Please specify CSS selector.",
                    "method": "playwright",
                    "needs_selectors": True,
                    "detected_fields": debug_fields,
                }

            # Find password field
            password_el = None
            if password_selector:
                try:
                    password_el = page.locator(password_selector).first
                    if await password_el.count() == 0:
                        password_el = None
                except Exception:
                    pass

            if not password_el:
                for sel in _PASSWORD_SELECTORS:
                    try:
                        loc = page.locator(sel).first
                        if await loc.count() > 0 and await loc.is_visible():
                            password_el = loc
                            break
                    except Exception:
                        continue

            # Generic fallback for password: any visible password-type input
            if not password_el:
                try:
                    loc = page.locator('input[type="password"]:visible').first
                    if await loc.count() > 0:
                        password_el = loc
                        logger.info("Playwright: found password field via generic password type selector")
                except Exception:
                    pass

            if not password_el:
                await browser.close()
                return {
                    "success": False,
                    "error": "Could not find password field. Please specify CSS selector.",
                    "method": "playwright",
                    "needs_selectors": True,
                }

            # Fill fields with human-like typing
            await username_el.click()
            await asyncio.sleep(0.2)
            await username_el.fill("")
            await username_el.type(username, delay=random.randint(30, 80))

            await asyncio.sleep(0.3)

            await password_el.click()
            await asyncio.sleep(0.2)
            await password_el.fill("")
            await password_el.type(password, delay=random.randint(30, 80))

            await asyncio.sleep(0.5)

            # Find and click submit
            submit_el = None
            if submit_selector:
                try:
                    submit_el = page.locator(submit_selector).first
                    if await submit_el.count() == 0:
                        submit_el = None
                except Exception:
                    pass

            if not submit_el:
                for sel in _SUBMIT_SELECTORS:
                    try:
                        loc = page.locator(sel).first
                        if await loc.count() > 0 and await loc.is_visible():
                            submit_el = loc
                            break
                    except Exception:
                        continue

            if submit_el:
                await submit_el.click()
            else:
                # Try pressing Enter on the password field
                await password_el.press("Enter")

            # Wait for navigation / response
            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                await asyncio.sleep(3)

            await asyncio.sleep(1)

            # Extract cookies
            browser_cookies = await context.cookies()
            cookies = {}
            for c in browser_cookies:
                cookie_domain = c.get("domain", "").lstrip(".")
                if domain:
                    domain_clean = domain.lstrip(".")
                    if cookie_domain and domain_clean not in cookie_domain and cookie_domain not in domain_clean:
                        continue
                cookies[c["name"]] = c["value"]

            final_url = page.url
            page_content = await page.content()
            body_lower = page_content.lower()

            has_error = any(w in body_lower for w in _LOGIN_FAIL_INDICATORS)
            has_dashboard = any(
                w in body_lower
                for w in ["dashboard", "welcome", "logout", "sign out", "my account",
                          "панель", "выйти", "профиль"]
            )

            login_url_base = login_url.rstrip("/").split("?")[0]
            final_url_base = final_url.rstrip("/").split("?")[0]
            is_redirect_away = login_url_base != final_url_base

            # Check if we're still on a login page (has password field + login text)
            still_on_login_page = (
                ('type="password"' in body_lower or "type='password'" in body_lower)
                and any(w in body_lower for w in ["sign in", "log in", "login", "войти", "авторизация", "вход"])
            )

            # Check for NEW cookies (not pre-existing CSRF/analytics)
            post_cookie_names = {c["name"] for c in browser_cookies}
            new_cookie_names = post_cookie_names - pre_login_cookie_names
            has_new_cookies = bool(new_cookie_names)

            # Check if page content changed significantly (not just re-render)
            content_changed = pre_login_content != page_content and not still_on_login_page

            await browser.close()

            logger.info(
                f"Playwright login: redirect={is_redirect_away} "
                f"cookies={len(cookies)} new_cookies={len(new_cookie_names)} "
                f"error={has_error} dashboard={has_dashboard} "
                f"still_on_login={still_on_login_page} content_changed={content_changed}"
            )

            # Definite failure: explicit error or still on login page with no change
            if has_error:
                return {"success": False, "error": "Invalid credentials detected in browser", "method": "playwright"}

            if still_on_login_page and not is_redirect_away and not has_dashboard:
                return {"success": False, "error": "Still on login page after submit — credentials likely incorrect", "method": "playwright"}

            # Confident success: redirected away or dashboard found with cookies
            if cookies and (is_redirect_away or has_dashboard):
                return {
                    "success": True,
                    "cookies": cookies,
                    "method": "playwright",
                    "final_url": final_url,
                }

            # Moderate confidence: new cookies appeared and we navigated away
            if has_new_cookies and (is_redirect_away or content_changed):
                return {
                    "success": True,
                    "cookies": cookies,
                    "method": "playwright",
                    "final_url": final_url,
                    "warning": "Login likely succeeded (new cookies set, page changed)",
                }

            # Low confidence: only pre-existing cookies, no clear change
            if not has_new_cookies and not is_redirect_away and not has_dashboard:
                return {"success": False, "error": "No new session cookies after login — credentials likely incorrect", "method": "playwright"}

            # Fallback: cookies exist but can't confirm
            if cookies and not still_on_login_page:
                return {
                    "success": True,
                    "cookies": cookies,
                    "method": "playwright",
                    "final_url": final_url,
                    "warning": "Login may have succeeded but couldn't fully confirm",
                }

            return {"success": False, "error": "Login failed — no clear indication of successful authentication", "method": "playwright"}

    except Exception as e:
        logger.exception(f"Playwright login error: {e}")
        return {"success": False, "error": f"Browser login error: {str(e)}", "method": "playwright"}


# ──────────────────────────────────────────────────────────────────────────────
# Interactive Login — click login button on homepage, wait for form, fill & submit
# ──────────────────────────────────────────────────────────────────────────────

# Common selectors for login/sign-in buttons on homepages
_LOGIN_BUTTON_SELECTORS = [
    'a[href*="login"]',
    'a[href*="signin"]',
    'a[href*="sign-in"]',
    'a[href*="auth"]',
    'button:has-text("Log in")',
    'button:has-text("Sign in")',
    'a:has-text("Log in")',
    'a:has-text("Sign in")',
    'a:has-text("Login")',
    'a:has-text("Sign In")',
    'a:has-text("Войти")',
    'a:has-text("Авторизация")',
    '[data-testid*="login"]',
    '[data-testid*="signin"]',
    '.login-btn',
    '.sign-in-btn',
    '#login-link',
    '#signin-link',
]


async def interactive_login(
    home_url: str,
    username: str,
    password: str,
    login_button_selector: str = "",
    username_selector: str = "",
    password_selector: str = "",
    submit_selector: str = "",
    domain: str = "",
) -> dict:
    """
    Interactive Login flow using Playwright:
      1. Navigate to the homepage (or a page with login button)
      2. Click the login button (user-provided or auto-detected)
      3. Wait for login form to appear (handles modals, SPAs, redirects)
      4. Auto-detect username/password fields
      5. Fill credentials with human-like typing
      6. Submit the form
      7. Extract cookies from browser context

    This handles:
      - Login modals (click button → modal appears with form)
      - SPA login (click → JS renders a login form)
      - Redirect to login page (click → navigate to /login)
      - Multi-page flows (homepage → login page)
    """
    if not _PLAYWRIGHT_AVAILABLE:
        return {
            "success": False,
            "error": "Playwright not installed — interactive login unavailable",
            "method": "interactive",
        }

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            context = await browser.new_context(
                user_agent=get_random_ua(),
                viewport={"width": 1366, "height": 768},
                locale="en-US",
                timezone_id="America/New_York",
            )

            page = await context.new_page()

            # Remove webdriver detection
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => false });
                delete navigator.__proto__.webdriver;
            """)

            # Step 1: Navigate to homepage
            logger.info(f"Interactive login: navigating to {home_url}")
            try:
                await page.goto(home_url, wait_until="domcontentloaded", timeout=45000)
            except Exception as nav_err:
                logger.warning(f"Interactive login: goto with domcontentloaded failed, retrying with commit: {nav_err}")
                await page.goto(home_url, wait_until="commit", timeout=30000)
            # Wait for dynamic content to load
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass  # Don't fail if networkidle times out
            await asyncio.sleep(1)

            # Step 2: Find and click the login button
            login_btn = None

            if login_button_selector:
                try:
                    login_btn = page.locator(login_button_selector).first
                    if await login_btn.count() == 0:
                        login_btn = None
                        logger.warning(f"Interactive login: user selector '{login_button_selector}' not found")
                except Exception as e:
                    logger.warning(f"Interactive login: error with user selector: {e}")

            if not login_btn:
                for sel in _LOGIN_BUTTON_SELECTORS:
                    try:
                        loc = page.locator(sel).first
                        if await loc.count() > 0 and await loc.is_visible():
                            login_btn = loc
                            logger.info(f"Interactive login: found login button via selector: {sel}")
                            break
                    except Exception:
                        continue

            if not login_btn:
                await browser.close()
                return {
                    "success": False,
                    "error": "Could not find login button on the page. Please provide a CSS selector for the login button.",
                    "method": "interactive",
                    "needs_login_button_selector": True,
                }

            # Click the login button
            logger.info("Interactive login: clicking login button...")
            await login_btn.click()

            # Step 3: Wait for login form to appear
            # This handles modals, SPA rendering, and page redirects
            password_field_found = False

            for attempt in range(15):  # Wait up to ~15 seconds
                await asyncio.sleep(1)
                try:
                    pwd_loc = page.locator('input[type="password"]:visible').first
                    if await pwd_loc.count() > 0:
                        password_field_found = True
                        logger.info(f"Interactive login: password field appeared after {attempt + 1}s")
                        break
                except Exception:
                    continue

            if not password_field_found:
                # Try waiting for page navigation (redirect to login page)
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=5000)
                    await asyncio.sleep(2)
                    pwd_loc = page.locator('input[type="password"]:visible').first
                    if await pwd_loc.count() > 0:
                        password_field_found = True
                except Exception:
                    pass

            if not password_field_found:
                # Collect debug info about what's on the page
                page_url = page.url
                debug_inputs = []
                try:
                    all_inputs = page.locator('input:visible')
                    count = await all_inputs.count()
                    for i in range(min(count, 10)):
                        inp = all_inputs.nth(i)
                        debug_inputs.append({
                            "type": await inp.get_attribute("type") or "text",
                            "name": await inp.get_attribute("name") or "",
                            "id": await inp.get_attribute("id") or "",
                            "placeholder": await inp.get_attribute("placeholder") or "",
                        })
                except Exception:
                    pass

                await browser.close()
                return {
                    "success": False,
                    "error": f"Login form did not appear after clicking login button. Current URL: {page_url}. Visible inputs: {debug_inputs}",
                    "method": "interactive",
                    "current_url": page_url,
                    "detected_fields": debug_inputs,
                }

            # Step 4: Find and fill username field
            await asyncio.sleep(0.5)  # Brief stabilization wait

            username_el = None
            if username_selector:
                try:
                    username_el = page.locator(username_selector).first
                    if await username_el.count() == 0:
                        username_el = None
                except Exception:
                    pass

            if not username_el:
                for sel in _USERNAME_SELECTORS:
                    try:
                        loc = page.locator(sel).first
                        if await loc.count() > 0 and await loc.is_visible():
                            username_el = loc
                            break
                    except Exception:
                        continue

            # Generic fallback: first visible text/email input
            if not username_el:
                try:
                    all_inputs = page.locator('input:visible')
                    count = await all_inputs.count()
                    for i in range(count):
                        inp = all_inputs.nth(i)
                        inp_type = (await inp.get_attribute("type") or "text").lower()
                        if inp_type in ("text", "email", "tel", ""):
                            username_el = inp
                            break
                except Exception:
                    pass

            if not username_el:
                await browser.close()
                return {
                    "success": False,
                    "error": "Login form appeared but could not find username field. Please specify username CSS selector.",
                    "method": "interactive",
                    "needs_selectors": True,
                }

            # Find password field
            password_el = None
            if password_selector:
                try:
                    password_el = page.locator(password_selector).first
                    if await password_el.count() == 0:
                        password_el = None
                except Exception:
                    pass

            if not password_el:
                try:
                    password_el = page.locator('input[type="password"]:visible').first
                    if await password_el.count() == 0:
                        password_el = None
                except Exception:
                    pass

            if not password_el:
                await browser.close()
                return {
                    "success": False,
                    "error": "Could not find password field after form appeared.",
                    "method": "interactive",
                    "needs_selectors": True,
                }

            # Step 5: Fill fields with human-like typing
            await username_el.click()
            await asyncio.sleep(0.2)
            await username_el.fill("")
            await username_el.type(username, delay=random.randint(30, 80))

            await asyncio.sleep(0.3)

            await password_el.click()
            await asyncio.sleep(0.2)
            await password_el.fill("")
            await password_el.type(password, delay=random.randint(30, 80))

            await asyncio.sleep(0.5)

            # Step 6: Find and click submit
            submit_el = None
            if submit_selector:
                try:
                    submit_el = page.locator(submit_selector).first
                    if await submit_el.count() == 0:
                        submit_el = None
                except Exception:
                    pass

            if not submit_el:
                for sel in _SUBMIT_SELECTORS:
                    try:
                        loc = page.locator(sel).first
                        if await loc.count() > 0 and await loc.is_visible():
                            submit_el = loc
                            break
                    except Exception:
                        continue

            if submit_el:
                await submit_el.click()
            else:
                await password_el.press("Enter")

            # Wait for navigation
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception:
                pass
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                await asyncio.sleep(3)

            await asyncio.sleep(1)

            # Step 7: Extract cookies & verify
            browser_cookies = await context.cookies()
            cookies = {}
            for c in browser_cookies:
                cookie_domain = c.get("domain", "").lstrip(".")
                if domain:
                    domain_clean = domain.lstrip(".")
                    if cookie_domain and domain_clean not in cookie_domain and cookie_domain not in domain_clean:
                        continue
                cookies[c["name"]] = c["value"]

            final_url = page.url
            page_content = await page.content()
            body_lower = page_content.lower()

            has_error = any(w in body_lower for w in _LOGIN_FAIL_INDICATORS)
            has_dashboard = any(
                w in body_lower
                for w in ["dashboard", "welcome", "logout", "sign out", "my account",
                          "панель", "выйти", "профиль"]
            )

            home_url_base = home_url.rstrip("/").split("?")[0]
            final_url_base = final_url.rstrip("/").split("?")[0]
            is_redirect_away = home_url_base != final_url_base

            await browser.close()

            logger.info(
                f"Interactive login: redirect={is_redirect_away} "
                f"cookies={len(cookies)} error={has_error} dashboard={has_dashboard}"
            )

            if cookies and (is_redirect_away or has_dashboard) and not has_error:
                return {
                    "success": True,
                    "cookies": cookies,
                    "method": "interactive",
                    "final_url": final_url,
                }
            elif cookies and not has_error:
                return {
                    "success": True,
                    "cookies": cookies,
                    "method": "interactive",
                    "final_url": final_url,
                    "warning": "Login may have succeeded (cookies set, no error detected)",
                }
            else:
                msg = "Interactive login failed"
                if has_error:
                    msg = "Invalid credentials detected after interactive login"
                elif not cookies:
                    msg = "No cookies set after interactive login"
                return {"success": False, "error": msg, "method": "interactive"}

    except Exception as e:
        logger.exception(f"Interactive login error: {e}")
        return {"success": False, "error": f"Interactive login error: {str(e)}", "method": "interactive"}


# ──────────────────────────────────────────────────────────────────────────────
# Recorded Flow Login — replay a sequence of recorded user actions
# ──────────────────────────────────────────────────────────────────────────────

async def recorded_flow_login(
    steps: list[dict],
    username: str = "",
    password: str = "",
    domain: str = "",
) -> dict:
    """
    Replay a recorded login flow using Playwright.

    Each step is a dict with:
      - action: "goto" | "click" | "type" | "select" | "wait" | "press" | "check"
      - selector: CSS/Playwright selector (for click, type, select, press, check)
      - value: value to type or URL to goto. Supports placeholders:
          - {{USER_INPUT}} → replaced with actual username
          - {{PASSWORD_INPUT}} → replaced with actual password
      - wait_ms: milliseconds to wait (for "wait" action)
      - description: optional human-readable description of the step

    Example steps:
      [
        {"action": "goto", "value": "https://example.com/login"},
        {"action": "click", "selector": "#loginBtn"},
        {"action": "wait", "wait_ms": 2000},
        {"action": "type", "selector": "#email", "value": "{{USER_INPUT}}"},
        {"action": "type", "selector": "#password", "value": "{{PASSWORD_INPUT}}"},
        {"action": "click", "selector": "button[type=submit]"},
        {"action": "wait", "wait_ms": 3000}
      ]
    """
    if not _PLAYWRIGHT_AVAILABLE:
        return {
            "success": False,
            "error": "Playwright not installed — recorded flow unavailable",
            "method": "recorded",
        }

    if not steps:
        return {
            "success": False,
            "error": "No steps provided for recorded flow",
            "method": "recorded",
        }

    step_results = []

    def _substitute(value: str) -> str:
        """Replace placeholders with actual credentials."""
        if not value:
            return value
        return value.replace("{{USER_INPUT}}", username).replace("{{PASSWORD_INPUT}}", password)

    # Data extracted from browser — initialised here so analysis
    # can run even after a Playwright crash mid-extraction.
    browser_cookies: list[dict] = []
    cookies: dict[str, str] = {}
    all_cookie_names: list[str] = []
    final_url = ""
    body_lower = ""
    storage_tokens: dict = {}
    pre_login_cookie_names: set[str] = set()

    pw = None
    browser = None

    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        context = await browser.new_context(
            user_agent=get_random_ua(),
            viewport={"width": 1366, "height": 768},
            locale="en-US",
            timezone_id="America/New_York",
        )

        page = await context.new_page()

        # Remove webdriver detection
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            delete navigator.__proto__.webdriver;
        """)

        # ── Step replay ───────────────────────────────────────────
        for i, step in enumerate(steps):
            action = step.get("action", "").lower()
            selector = step.get("selector", "")
            value = _substitute(step.get("value", ""))
            wait_ms = step.get("wait_ms", 1000)

            # Capture cookies right after first page load (before any login action)
            if i == 0 and action == "goto":
                pass  # Will capture after goto completes
            elif i == 1 and not pre_login_cookie_names:
                try:
                    pre_cookies = await context.cookies()
                    pre_login_cookie_names = {c["name"] for c in pre_cookies}
                except Exception:
                    pass

            logger.info(f"Recorded flow step {i + 1}/{len(steps)}: {action} {selector or value}")

            try:
                # ── Check if page crashed before doing anything ──
                if action != "goto":
                    try:
                        cur = page.url
                        if cur.startswith("chrome-error://"):
                            logger.warning(f"Recorded flow step {i + 1}: page on chrome-error, attempting recovery")
                            goto_url = f"https://{domain}" if domain else ""
                            for s in steps:
                                if s.get("action") == "goto" and s.get("value"):
                                    goto_url = s["value"]
                                    break
                            if goto_url:
                                try:
                                    page = await context.new_page()
                                    await page.add_init_script("""
                                        Object.defineProperty(navigator, 'webdriver', { get: () => false });
                                        delete navigator.__proto__.webdriver;
                                    """)
                                    await page.goto(goto_url, wait_until="commit", timeout=30000)
                                    await asyncio.sleep(2)
                                    logger.info(f"Recovered from chrome-error, now on {page.url}")
                                except Exception as rec_err:
                                    logger.warning(f"Failed to recover from chrome-error: {rec_err}")
                    except Exception:
                        pass

                if action == "goto":
                    # Try loading with increasing fallback
                    goto_ok = False
                    for goto_attempt in range(3):
                        try:
                            if goto_attempt == 0:
                                await page.goto(value, wait_until="domcontentloaded", timeout=45000)
                            elif goto_attempt == 1:
                                await page.goto(value, wait_until="commit", timeout=30000)
                            else:
                                # Last resort — new page
                                page = await context.new_page()
                                await page.add_init_script("""
                                    Object.defineProperty(navigator, 'webdriver', { get: () => false });
                                    delete navigator.__proto__.webdriver;
                                """)
                                await page.goto(value, wait_until="commit", timeout=30000)
                        except Exception as goto_err:
                            if goto_attempt < 2:
                                logger.warning(f"Recorded flow goto attempt {goto_attempt + 1} failed: {goto_err}")
                                await asyncio.sleep(2)
                                continue
                            raise

                        # Check for chrome-error:// crash page
                        current_url = ""
                        try:
                            current_url = page.url
                        except Exception:
                            pass

                        if current_url.startswith("chrome-error://"):
                            logger.warning(f"Recorded flow: browser crashed to {current_url}, retrying (attempt {goto_attempt + 1}/3)")
                            await asyncio.sleep(3)
                            if goto_attempt < 2:
                                continue
                            step_results.append({"step": i + 1, "action": action, "status": "error", "detail": f"Browser crashed: {current_url}"})
                            goto_ok = False
                            break
                        else:
                            goto_ok = True
                            break

                    if goto_ok:
                        try:
                            await page.wait_for_load_state("networkidle", timeout=10000)
                        except Exception:
                            pass
                        step_results.append({"step": i + 1, "action": action, "status": "ok", "detail": f"Navigated to {value}"})

                    # Capture pre-login cookies right after first page load
                    if i == 0 and not pre_login_cookie_names:
                        try:
                            pre_cookies = await context.cookies()
                            pre_login_cookie_names = {c["name"] for c in pre_cookies}
                            logger.info(f"Pre-login cookies captured: {len(pre_login_cookie_names)}")
                        except Exception:
                            pass

                elif action == "click":
                    if not selector:
                        step_results.append({"step": i + 1, "action": action, "status": "error", "detail": "No selector provided"})
                        continue
                    loc = page.locator(selector).first
                    if await loc.count() == 0:
                        try:
                            await page.wait_for_selector(selector, state="visible", timeout=5000)
                            loc = page.locator(selector).first
                        except Exception:
                            step_results.append({"step": i + 1, "action": action, "status": "error", "detail": f"Element not found: {selector}"})
                            continue
                    await loc.click()
                    try:
                        await page.wait_for_load_state("networkidle", timeout=10000)
                    except Exception:
                        await asyncio.sleep(1)
                    step_results.append({"step": i + 1, "action": action, "status": "ok", "detail": f"Clicked {selector}"})

                elif action == "type":
                    if not selector:
                        step_results.append({"step": i + 1, "action": action, "status": "error", "detail": "No selector provided"})
                        continue
                    loc = page.locator(selector).first
                    if await loc.count() == 0:
                        try:
                            await page.wait_for_selector(selector, state="visible", timeout=5000)
                            loc = page.locator(selector).first
                        except Exception:
                            step_results.append({"step": i + 1, "action": action, "status": "error", "detail": f"Element not found: {selector}"})
                            continue
                    is_credential = "USER_INPUT" in step.get("value", "") or "PASSWORD_INPUT" in step.get("value", "")
                    display_value = "***" if is_credential else value

                    typed_ok = False
                    try:
                        await loc.click()
                        await asyncio.sleep(0.1)
                        await loc.fill(value)
                        actual = await loc.input_value(timeout=1000)
                        if actual == value or (is_credential and actual):
                            typed_ok = True
                    except Exception:
                        pass
                    if not typed_ok:
                        try:
                            await loc.click()
                            await asyncio.sleep(0.1)
                            await page.keyboard.press("Control+a")
                            await page.keyboard.press("Backspace")
                            await asyncio.sleep(0.1)
                            await loc.type(value, delay=random.randint(50, 120))
                            actual = await loc.input_value(timeout=1000)
                            if actual == value or (is_credential and actual):
                                typed_ok = True
                        except Exception:
                            pass
                    if not typed_ok:
                        try:
                            await loc.focus()
                            await asyncio.sleep(0.1)
                            await page.keyboard.press("Control+a")
                            await page.keyboard.press("Backspace")
                            await asyncio.sleep(0.1)
                            await page.keyboard.type(value, delay=random.randint(50, 120))
                            typed_ok = True
                        except Exception:
                            pass
                    if not typed_ok:
                        try:
                            await page.evaluate("""
                                (args) => {
                                    const el = document.querySelector(args.selector);
                                    if (!el) return;
                                    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                                        window.HTMLInputElement.prototype, 'value'
                                    ).set;
                                    nativeInputValueSetter.call(el, args.value);
                                    el.dispatchEvent(new Event('input', { bubbles: true }));
                                    el.dispatchEvent(new Event('change', { bubbles: true }));
                                }
                            """, {"selector": selector, "value": value})
                            typed_ok = True
                        except Exception as js_err:
                            logger.warning(f"JS value set failed for {selector}: {js_err}")
                    status = "ok" if typed_ok else "warning"
                    step_results.append({"step": i + 1, "action": action, "status": status, "detail": f"Typed '{display_value}' into {selector}"})

                elif action == "select":
                    if not selector:
                        step_results.append({"step": i + 1, "action": action, "status": "error", "detail": "No selector provided"})
                        continue
                    loc = page.locator(selector).first
                    await loc.select_option(value)
                    step_results.append({"step": i + 1, "action": action, "status": "ok", "detail": f"Selected '{value}' in {selector}"})

                elif action == "press":
                    if selector:
                        loc = page.locator(selector).first
                        await loc.press(value)
                    else:
                        await page.keyboard.press(value)
                    step_results.append({"step": i + 1, "action": action, "status": "ok", "detail": f"Pressed {value}"})

                elif action == "check":
                    if not selector:
                        step_results.append({"step": i + 1, "action": action, "status": "error", "detail": "No selector provided"})
                        continue
                    loc = page.locator(selector).first
                    await loc.check()
                    step_results.append({"step": i + 1, "action": action, "status": "ok", "detail": f"Checked {selector}"})

                elif action == "wait":
                    ms = int(wait_ms)
                    await asyncio.sleep(ms / 1000)
                    step_results.append({"step": i + 1, "action": action, "status": "ok", "detail": f"Waited {ms}ms"})

                elif action == "wait_for":
                    if not selector:
                        step_results.append({"step": i + 1, "action": action, "status": "error", "detail": "No selector provided"})
                        continue
                    timeout_ms = int(wait_ms) if wait_ms else 10000
                    await page.wait_for_selector(selector, state="visible", timeout=timeout_ms)
                    step_results.append({"step": i + 1, "action": action, "status": "ok", "detail": f"Element appeared: {selector}"})

                else:
                    step_results.append({"step": i + 1, "action": action, "status": "warning", "detail": f"Unknown action: {action}"})

                await asyncio.sleep(random.uniform(0.2, 0.5))

            except Exception as e:
                logger.warning(f"Recorded flow step {i + 1} failed: {e}")
                step_results.append({"step": i + 1, "action": action, "status": "error", "detail": str(e)})

        # ── Extract data from browser BEFORE closing ─────────────
        # Each operation is individually protected; a crashed page
        # must not prevent cookie extraction from the context.

        # 1. Wait for page to settle (SPA apps)
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=8000)
        except Exception:
            pass
        try:
            await page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass

        await asyncio.sleep(2)

        # 2. Cookies — try context.cookies() (works even if page crashed)
        try:
            browser_cookies = await context.cookies()
            for c in browser_cookies:
                all_cookie_names.append(f"{c['name']}(domain={c.get('domain', '')})")
                cookie_domain = c.get("domain", "").lstrip(".")
                if domain:
                    domain_clean = domain.lstrip(".")
                    if cookie_domain and domain_clean not in cookie_domain and cookie_domain not in domain_clean:
                        continue
                cookies[c["name"]] = c["value"]
            logger.info(
                f"Recorded flow cookies: {len(cookies)} matched out of "
                f"{len(browser_cookies)} total. All: {', '.join(all_cookie_names[:20])}"
            )
        except Exception as cookie_err:
            logger.warning(f"Recorded flow: context.cookies() failed: {cookie_err}")
            # Fallback: open a fresh page to re-establish context, then retry
            try:
                fb_page = await context.new_page()
                await fb_page.goto(f"https://{domain}", wait_until="commit", timeout=15000)
                await asyncio.sleep(1)
                browser_cookies = await context.cookies()
                for c in browser_cookies:
                    all_cookie_names.append(f"{c['name']}(domain={c.get('domain', '')})")
                    cookie_domain = c.get("domain", "").lstrip(".")
                    if domain:
                        domain_clean = domain.lstrip(".")
                        if cookie_domain and domain_clean not in cookie_domain and cookie_domain not in domain_clean:
                            continue
                    cookies[c["name"]] = c["value"]
                logger.info(f"Recorded flow: fallback cookie extraction got {len(cookies)} cookies")
            except Exception as fb_err:
                logger.warning(f"Recorded flow: fallback cookie extraction also failed: {fb_err}")

        # 3. Page URL
        try:
            final_url = page.url
        except Exception:
            logger.warning("Recorded flow: could not get final URL (page closed)")

        # 4. Page content
        try:
            page_content = await page.content()
            body_lower = page_content.lower()
        except Exception:
            logger.warning("Recorded flow: could not get page content (page closed)")

        # 5. Storage tokens (JWT etc.)
        try:
            storage_data = await page.evaluate("""
                () => {
                    const result = {};
                    const tokenKeys = ['token', 'access_token', 'auth_token', 'jwt',
                                      'session', 'sid', 'user', 'auth'];
                    for (let i = 0; i < localStorage.length; i++) {
                        const key = localStorage.key(i);
                        if (tokenKeys.some(tk => key.toLowerCase().includes(tk))) {
                            result['ls_' + key] = localStorage.getItem(key);
                        }
                    }
                    for (let i = 0; i < sessionStorage.length; i++) {
                        const key = sessionStorage.key(i);
                        if (tokenKeys.some(tk => key.toLowerCase().includes(tk))) {
                            result['ss_' + key] = sessionStorage.getItem(key);
                        }
                    }
                    return result;
                }
            """)
            if storage_data:
                storage_tokens = storage_data
        except Exception:
            logger.warning("Recorded flow: could not extract storage tokens (page closed)")

    except Exception as e:
        # Catch-all for Playwright crashes (context closed, browser died, etc.)
        # We still continue to analysis with whatever data we managed to extract.
        logger.warning(f"Recorded flow: Playwright crash during replay/extraction: {e}")

    finally:
        # ── ALWAYS close browser and Playwright ──────────────────
        try:
            if browser:
                await browser.close()
        except Exception:
            pass
        try:
            if pw:
                await pw.stop()
        except Exception:
            pass

    # ── Analyse extracted data (no browser needed) ────────────────
    failed_steps = sum(1 for s in step_results if s["status"] == "error")
    all_tokens = {**cookies, **storage_tokens}

    _EXPLICIT_FAIL_PATTERNS = [
        "invalid password", "invalid credentials", "invalid login",
        "incorrect password", "incorrect username",
        "wrong password", "wrong credentials",
        "login failed", "authentication failed",
        "bad credentials", "access denied",
        "неверный пароль", "неверный логин", "неверные данные",
        "неправильный пароль", "ошибка авторизации",
        "попробуйте снова", "try again",
        "please enter a correct",
    ]
    has_explicit_error = any(p in body_lower for p in _EXPLICIT_FAIL_PATTERNS) if body_lower else False

    has_dashboard = any(
        w in body_lower
        for w in ["dashboard", "welcome", "logout", "sign out", "my account",
                  "панель", "выйти", "профиль", "admin", "settings",
                  "настройки", "управление"]
    ) if body_lower else False

    login_url_indicators = ["login", "signin", "sign-in", "auth", "вход"]
    first_step_url = ""
    for s in steps:
        if s.get("action") == "goto" and s.get("value"):
            first_step_url = s["value"]
            break
    was_on_login = any(ind in first_step_url.lower() for ind in login_url_indicators)
    still_on_login = any(ind in final_url.lower() for ind in login_url_indicators) if final_url else False
    redirected_away = was_on_login and not still_on_login

    logger.info(
        f"Recorded flow: cookies={len(cookies)} storage_tokens={len(storage_tokens)} "
        f"explicit_error={has_explicit_error} dashboard={has_dashboard} "
        f"redirected_away={redirected_away} failed_steps={failed_steps}/{len(steps)}"
    )

    still_on_login_page = False
    if body_lower:
        still_on_login_page = (
            ('type="password"' in body_lower or "type='password'" in body_lower)
            and any(w in body_lower for w in ["sign in", "log in", "login", "войти", "авторизация", "вход"])
        )

    post_cookie_names = {c["name"] for c in browser_cookies}
    new_cookie_names = post_cookie_names - pre_login_cookie_names
    has_new_cookies = bool(new_cookie_names)

    logger.info(
        f"Recorded flow: pre_cookies={len(pre_login_cookie_names)} "
        f"post_cookies={len(post_cookie_names)} new_cookies={len(new_cookie_names)} "
        f"still_on_login_page={still_on_login_page}"
    )

    login_success = False
    if has_explicit_error:
        login_success = False
    elif still_on_login_page and not redirected_away and not has_dashboard:
        login_success = False
    elif has_new_cookies and (redirected_away or has_dashboard or not still_on_login_page):
        login_success = True
    elif storage_tokens:
        login_success = True
    elif redirected_away and has_dashboard:
        login_success = True
    elif redirected_away and not still_on_login and has_new_cookies:
        login_success = True
    elif cookies and not still_on_login_page and (redirected_away or has_dashboard):
        login_success = True

    if login_success:
        return {
            "success": True,
            "cookies": cookies,
            "storage_tokens": storage_tokens,
            "method": "recorded",
            "final_url": final_url,
            "steps_executed": len(steps),
            "steps_failed": failed_steps,
            "step_results": step_results,
        }
    else:
        msg = "Recorded flow login failed"
        if has_explicit_error:
            msg = "Invalid credentials detected after recorded flow"
        elif not all_tokens:
            msg = (
                f"No cookies or auth tokens found after replay. "
                f"Final URL: {final_url}. "
                f"Browser had {len(browser_cookies)} cookies total "
                f"(0 matched domain '{domain}')"
            )
        elif failed_steps > 0:
            msg = f"{failed_steps}/{len(steps)} steps failed during replay"
        return {
            "success": False,
            "error": msg,
            "method": "recorded",
            "final_url": final_url,
            "step_results": step_results,
        }


# ──────────────────────────────────────────────────────────────────────────────

async def perform_login(
    session: aiohttp.ClientSession,
    auth_config: dict,
    domain: str = "",
) -> dict:
    """
    Perform login with automatic fallback:
      1. Try HTTP form login
      2. If failed → try Playwright headless browser
      3. Return combined result with method used

    Supports auth_strategy:
      - "auto" (default): HTTP first → Playwright fallback
      - "http_only": HTTP only, no Playwright fallback
      - "playwright_only": Skip HTTP, Playwright only

    For cookie auth: inject cookies and validate them.
    """
    auth_type = auth_config.get("auth_type", "none")

    if auth_type == "cookie":
        return await validate_and_inject_cookies(session, domain, auth_config.get("cookies", {}))

    # ── Interactive Login ──────────────────────────────────────────
    if auth_type == "interactive":
        home_url = auth_config.get("home_url", "") or auth_config.get("login_url", "")
        username = auth_config.get("username", "")
        password = auth_config.get("password", "")
        if not home_url or not username or not password:
            return {"success": False, "error": "home_url (or login_url), username, and password are required for interactive login"}

        result = await interactive_login(
            home_url=home_url,
            username=username,
            password=password,
            login_button_selector=auth_config.get("login_button_selector", ""),
            username_selector=auth_config.get("username_selector", ""),
            password_selector=auth_config.get("password_selector", ""),
            submit_selector=auth_config.get("submit_selector", ""),
            domain=domain,
        )

        if result.get("success"):
            # Inject cookies into the aiohttp session
            for k, v in result.get("cookies", {}).items():
                session.cookie_jar.update_cookies({k: v})
            logger.info(f"Interactive login succeeded for {domain}")
        return result

    # ── Recorded Flow Login ────────────────────────────────────────
    if auth_type == "recorded":
        steps = auth_config.get("recorded_steps", [])
        username = auth_config.get("username", "")
        password = auth_config.get("password", "")
        if not steps:
            return {"success": False, "error": "recorded_steps are required for recorded flow"}

        # Retry up to 3 times for transient browser/context crashes
        last_result = None
        for attempt in range(1, 4):
            result = await recorded_flow_login(
                steps=steps,
                username=username,
                password=password,
                domain=domain,
            )
            last_result = result

            if result.get("success"):
                for k, v in result.get("cookies", {}).items():
                    session.cookie_jar.update_cookies({k: v})
                logger.info(f"Recorded flow login succeeded for {domain} (attempt {attempt})")
                return result

            error_msg = result.get("error", "")
            # Retry only on transient browser/context crashes
            is_transient = any(kw in error_msg.lower() for kw in [
                "has been closed", "target page", "browser",
                "context", "connection refused", "timeout",
                "no cookies", "chrome-error", "net::",
            ])
            if is_transient and attempt < 3:
                logger.warning(
                    f"Recorded flow attempt {attempt} failed (transient): {error_msg}. Retrying..."
                )
                await asyncio.sleep(2)
                continue
            else:
                break

        return last_result

    if auth_type != "form":
        return {"success": False, "error": f"Unsupported auth type: {auth_type}"}

    login_url = auth_config.get("login_url", "")
    username = auth_config.get("username", "")
    password = auth_config.get("password", "")
    username_selector = auth_config.get("username_selector", "")
    password_selector = auth_config.get("password_selector", "")
    submit_selector = auth_config.get("submit_selector", "")
    strategy = auth_config.get("auth_strategy", "auto")

    if not login_url or not username or not password:
        return {"success": False, "error": "login_url, username, and password are required"}

    http_error = ""

    # Step 1: Try HTTP form login (unless playwright_only)
    if strategy in ("auto", "http_only"):
        logger.info(f"Attempting HTTP form login for {domain}")
        result = await http_form_login(
            session, login_url, username, password,
            username_selector, password_selector, submit_selector,
        )

        if result.get("success"):
            logger.info(f"HTTP login succeeded for {domain}")
            return result

        http_error = result.get("error", "")
        if strategy == "http_only":
            logger.warning(f"HTTP-only login failed for {domain}: {http_error}")
            return result

        logger.warning(f"HTTP login failed for {domain}: {http_error}. Trying Playwright fallback...")

    # Step 2: Playwright (for auto fallback or playwright_only)
    if strategy in ("auto", "playwright_only"):
        if _PLAYWRIGHT_AVAILABLE:
            pw_result = await playwright_form_login(
                login_url, username, password,
                username_selector, password_selector, submit_selector,
                domain=domain,
            )

            if pw_result.get("success"):
                # Inject Playwright cookies into the aiohttp session
                for k, v in pw_result.get("cookies", {}).items():
                    session.cookie_jar.update_cookies({k: v})
                logger.info(f"Playwright login succeeded for {domain}")
                return pw_result

            logger.warning(f"Playwright login also failed for {domain}: {pw_result.get('error')}")

            if strategy == "playwright_only":
                return pw_result

            return {
                "success": False,
                "error": f"Both login methods failed. HTTP: {http_error}. Browser: {pw_result.get('error', '')}",
                "method": "both_failed",
            }
        else:
            if strategy == "playwright_only":
                return {
                    "success": False,
                    "error": "Playwright not installed — cannot use playwright_only strategy",
                    "method": "playwright",
                    "playwright_available": False,
                }
            logger.warning("Playwright not available for fallback")
            return {
                "success": False,
                "error": f"HTTP login failed: {http_error}. Install Playwright for browser fallback.",
                "method": "http",
                "playwright_available": False,
            }

    return {"success": False, "error": f"Invalid auth_strategy: {strategy}"}


# ──────────────────────────────────────────────────────────────────────────────
# Cookie validation & injection
# ──────────────────────────────────────────────────────────────────────────────

async def validate_and_inject_cookies(
    session: aiohttp.ClientSession,
    domain: str,
    cookies: dict,
) -> dict:
    """
    Inject cookies into session and validate they give access.
    Tests against multiple protected paths and checks for login redirects.
    """
    if not cookies:
        return {"success": False, "error": "No cookies provided"}

    for key, value in cookies.items():
        session.cookie_jar.update_cookies({key: value})

    base_url = f"https://{domain}"
    accessible = 0
    tested = 0
    redirected_to_login = 0

    test_paths = ["/", "/admin/", "/dashboard/", "/account/", "/profile/",
                  "/settings/", "/user/", "/panel/"]

    for path in test_paths:
        try:
            async with session.get(
                base_url + path, allow_redirects=False, timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                tested += 1
                if resp.status == 200:
                    # Check if it's actually a login page disguised as 200
                    body = await resp.text(errors="replace")
                    body_lower = body.lower()
                    is_login_page = (
                        "input" in body_lower and "password" in body_lower
                        and any(w in body_lower for w in ["sign in", "log in", "login", "войти"])
                    )
                    if not is_login_page:
                        accessible += 1
                elif resp.status in (301, 302, 303, 307, 308):
                    location = resp.headers.get("Location", "").lower()
                    if any(w in location for w in ["login", "signin", "auth", "session"]):
                        redirected_to_login += 1
        except Exception:
            continue

    if accessible > 0:
        return {
            "success": True,
            "cookies": cookies,
            "method": "cookie",
            "pages_accessible": accessible,
            "pages_tested": tested,
        }

    if redirected_to_login > 0:
        return {
            "success": False,
            "error": f"Cookies expired or invalid — redirected to login on {redirected_to_login}/{tested} pages",
            "expired": True,
            "method": "cookie",
        }

    return {
        "success": False,
        "error": f"Cookies did not provide access to any of {tested} tested protected pages",
        "method": "cookie",
    }


# ──────────────────────────────────────────────────────────────────────────────
# Session validation during scan (detect expiry, trigger re-login)
# ──────────────────────────────────────────────────────────────────────────────

async def check_session_valid(
    session: aiohttp.ClientSession,
    domain: str,
) -> bool:
    """
    Quick check: is the current session still authenticated?
    First checks if we still have cookies in the jar (fast, no HTTP).
    Then tries a lightweight HTTP check on the main domain page.
    """
    # Fast check: do we still have cookies?
    cookie_count = 0
    for cookie in session.cookie_jar:
        cookie_count += 1
    if cookie_count == 0:
        logger.info(f"Session check: no cookies in jar for {domain}")
        return False

    # Light HTTP check: try main page, see if we get redirected to login
    base_url = f"https://{domain}"
    try:
        async with session.get(
            base_url, allow_redirects=False, timeout=aiohttp.ClientTimeout(total=8),
        ) as resp:
            # If we get 401/403 -> session expired
            if resp.status in (401, 403):
                return False
            # Redirect to login = session dead
            if resp.status in (301, 302, 303, 307):
                location = resp.headers.get("Location", "").lower()
                if any(w in location for w in ["login", "signin", "auth", "sign-in"]):
                    return False
            # 200 or any other status = likely OK (SPA returns 200 with shell)
            return True
    except Exception:
        # Network error — assume session is still valid (don't trigger re-login)
        return True


async def ensure_session(
    session: aiohttp.ClientSession,
    auth_config: dict,
    domain: str,
    force_relogin: bool = False,
) -> dict:
    """
    Ensure we have a valid authenticated session.
    Re-login only if necessary.

    Returns:
      {"valid": True/False, "relogin": True/False, "error": "..."}
    """
    if not force_relogin:
        is_valid = await check_session_valid(session, domain)
        if is_valid:
            return {"valid": True, "relogin": False}

    logger.info(f"Session expired or forced re-login for {domain}")

    # Clear old cookies before re-login
    session.cookie_jar.clear()

    result = await perform_login(session, auth_config, domain)
    if result.get("success"):
        return {"valid": True, "relogin": True, "cookies": result.get("cookies", {})}

    return {"valid": False, "relogin": True, "error": result.get("error", "Re-login failed")}


# ──────────────────────────────────────────────────────────────────────────────
# Improved Auth Test
# ──────────────────────────────────────────────────────────────────────────────

async def test_auth_config(auth_config: dict, domain: str) -> dict:
    """
    Comprehensive auth test:
      1. Perform login (HTTP → Playwright fallback)
      2. Verify session by accessing protected content
      3. Check for login redirects
      4. Return detailed result with method used, pages accessible, etc.
    """
    timeout = aiohttp.ClientTimeout(total=30)
    connector = aiohttp.TCPConnector(ssl=False)
    ua = get_random_ua()

    try:
        async with aiohttp.ClientSession(
            connector=connector, timeout=timeout,
            headers=get_realistic_headers(ua),
        ) as session:
            auth_type = auth_config.get("auth_type", "none")

            if auth_type in ("form", "interactive", "recorded"):
                result = await perform_login(session, auth_config, domain)
            elif auth_type == "cookie":
                result = await validate_and_inject_cookies(
                    session, domain, auth_config.get("cookies", {}),
                )
            else:
                return {"success": False, "error": f"Invalid auth_type: {auth_type}"}

            if not result.get("success"):
                return result

            # For SPA/JWT auth (recorded flow with storage tokens but no cookies),
            # skip HTTP verification — cookies won't work for token-based auth
            cookies = result.get("cookies", {})
            storage_tokens = result.get("storage_tokens", {})
            if auth_type == "recorded" and not cookies and storage_tokens:
                logger.info(f"SPA/JWT auth detected for {domain} — skipping HTTP cookie verification")
                result["method"] = "recorded_jwt"
                result["note"] = "JWT/token-based auth — cookies not applicable"
                return result

            base_url = f"https://{domain}"
            protected_pages = []
            login_redirects = []

            for path in ["/admin/", "/dashboard/", "/account/", "/profile/", "/"]:
                try:
                    async with session.get(
                        base_url + path, allow_redirects=False,
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as resp:
                        if resp.status == 200:
                            body = await resp.text(errors="replace")
                            body_lower = body.lower()
                            is_login = (
                                "password" in body_lower
                                and any(w in body_lower for w in ["sign in", "log in", "login"])
                            )
                            if not is_login:
                                protected_pages.append(path)
                        elif resp.status in (301, 302, 303, 307):
                            location = resp.headers.get("Location", "").lower()
                            if any(w in location for w in ["login", "signin", "auth"]):
                                login_redirects.append(path)
                except Exception:
                    continue

            result["pages_accessible"] = len(protected_pages)
            result["accessible_paths"] = protected_pages
            result["login_redirects"] = login_redirects
            result["cookies_count"] = len(cookies)

            if not protected_pages and login_redirects:
                result["success"] = False
                result["error"] = "Login appeared successful but all protected pages redirect to login"
                result["expired"] = True

            return result

    except Exception as e:
        logger.exception(f"Auth test failed for {domain}: {e}")
        return {"success": False, "error": str(e)}


# ──────────────────────────────────────────────────────────────────────────────
# URL checking during authenticated crawl
# ──────────────────────────────────────────────────────────────────────────────

def is_login_redirect(url: str, status_code: int) -> bool:
    """Check if a response is a redirect to a login page."""
    url_lower = url.lower()
    if status_code in (301, 302, 303, 307, 308):
        return any(w in url_lower for w in ["login", "signin", "auth", "session/new"])
    return False


def is_login_page_content(html: str) -> bool:
    """Check if HTML content looks like a login page."""
    lower = html.lower()
    has_password_field = 'type="password"' in lower or "type='password'" in lower
    has_login_text = any(w in lower for w in ["sign in", "log in", "login", "войти", "авторизация"])
    return has_password_field and has_login_text


# ──────────────────────────────────────────────────────────────────────────────
# Auth Debug — step-by-step login attempt with detailed logging
# ──────────────────────────────────────────────────────────────────────────────

async def debug_auth_login(auth_config: dict, domain: str) -> dict:
    """
    Perform a debug login attempt that returns step-by-step results.
    Every step is logged so the user can see exactly what happened.
    """
    steps = []
    strategy = auth_config.get("auth_strategy", "auto")
    auth_type = auth_config.get("auth_type", "none")

    def add_step(name: str, status: str, detail: str = "", data: dict = None):
        step = {"step": name, "status": status, "detail": detail}
        if data:
            step["data"] = data
        steps.append(step)

    add_step("init", "ok", f"Auth type: {auth_type}, Strategy: {strategy}")

    if auth_type == "cookie":
        cookies = auth_config.get("cookies", {})
        add_step("cookies_parse", "ok", f"Found {len(cookies)} cookie(s)", {"cookies": list(cookies.keys())})

        timeout = aiohttp.ClientTimeout(total=15)
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout, headers=get_realistic_headers()) as session:
            result = await validate_and_inject_cookies(session, domain, cookies)
            if result.get("success"):
                add_step("cookie_validation", "ok", f"{result.get('pages_accessible', 0)} pages accessible")
            else:
                add_step("cookie_validation", "failed", result.get("error", ""))

        return {"steps": steps, "success": result.get("success", False), "result": result}

    if auth_type not in ("form", "interactive", "recorded"):
        add_step("error", "failed", f"Unsupported auth type: {auth_type}")
        return {"steps": steps, "success": False}

    # ── Interactive login debug ────────────────────────────────────
    if auth_type == "interactive":
        home_url = auth_config.get("home_url", "") or auth_config.get("login_url", "")
        username = auth_config.get("username", "")
        password = auth_config.get("password", "")
        if not home_url or not username or not password:
            add_step("validation", "failed", "Missing home_url/login_url, username, or password")
            return {"steps": steps, "success": False}

        add_step("config", "ok", f"Home URL: {home_url}, Login button: {auth_config.get('login_button_selector', 'auto-detect')}")

        if not _PLAYWRIGHT_AVAILABLE:
            add_step("playwright_init", "failed", "Playwright not installed")
            return {"steps": steps, "success": False}

        add_step("playwright_init", "ok", "Playwright available, launching interactive login...")
        result = await interactive_login(
            home_url=home_url,
            username=username,
            password=password,
            login_button_selector=auth_config.get("login_button_selector", ""),
            username_selector=auth_config.get("username_selector", ""),
            password_selector=auth_config.get("password_selector", ""),
            submit_selector=auth_config.get("submit_selector", ""),
            domain=domain,
        )
        if result.get("success"):
            add_step("interactive_login", "ok", f"Interactive login succeeded! Final URL: {result.get('final_url', '')}")
        else:
            add_step("interactive_login", "failed", f"Interactive login failed: {result.get('error', '')}")
        return {"steps": steps, "success": result.get("success", False), "result": result}

    # ── Recorded flow debug ────────────────────────────────────────
    if auth_type == "recorded":
        recorded_steps = auth_config.get("recorded_steps", [])
        username = auth_config.get("username", "")
        password = auth_config.get("password", "")
        if not recorded_steps:
            add_step("validation", "failed", "No recorded steps provided")
            return {"steps": steps, "success": False}

        add_step("config", "ok", f"Recorded flow with {len(recorded_steps)} steps")

        if not _PLAYWRIGHT_AVAILABLE:
            add_step("playwright_init", "failed", "Playwright not installed")
            return {"steps": steps, "success": False}

        add_step("playwright_init", "ok", "Playwright available, replaying recorded flow...")
        result = await recorded_flow_login(
            steps=recorded_steps,
            username=username,
            password=password,
            domain=domain,
        )
        if result.get("success"):
            add_step("recorded_flow", "ok", f"Recorded flow succeeded! Final URL: {result.get('final_url', '')}")
        else:
            add_step("recorded_flow", "failed", f"Recorded flow failed: {result.get('error', '')}")

        # Include step-by-step replay results
        if result.get("step_results"):
            for sr in result["step_results"]:
                add_step(f"replay_step_{sr['step']}", sr["status"], sr.get("detail", ""))

        return {"steps": steps, "success": result.get("success", False), "result": result}

    # ── Form login debug (existing) ────────────────────────────────

    login_url = auth_config.get("login_url", "")
    username = auth_config.get("username", "")
    password = auth_config.get("password", "")

    if not login_url or not username or not password:
        add_step("validation", "failed", "Missing login_url, username, or password")
        return {"steps": steps, "success": False}

    add_step("config", "ok", f"Login URL: {login_url}, Username: {username}")

    # Step: Fetch login page
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout, headers=get_realistic_headers()) as session:
            async with session.get(login_url, allow_redirects=True) as resp:
                html = await resp.text(errors="replace")
                page_status = resp.status
                final_url = str(resp.url)

        add_step("fetch_login_page", "ok", f"Status: {page_status}, Final URL: {final_url}", {"status": page_status})

        soup = BeautifulSoup(html, "lxml")

        # Step: Find form
        form = _find_login_form(soup)
        if form:
            form_action = form.get("action", "")
            form_method = form.get("method", "POST")
            add_step("find_form", "ok", f"Form found: action={form_action}, method={form_method}")
        else:
            add_step("find_form", "warning", "No login form found on page")

        # Step: Detect fields
        username_field = _find_field(soup, auth_config.get("username_selector", ""), _USERNAME_SELECTORS, form)
        password_field = _find_field(soup, auth_config.get("password_selector", ""), _PASSWORD_SELECTORS, form)

        all_inputs = (form if form else soup).find_all("input")
        visible_inputs = [
            {"name": i.get("name", ""), "type": i.get("type", "text"), "id": i.get("id", ""), "placeholder": i.get("placeholder", "")}
            for i in all_inputs if i.get("type", "text") != "hidden"
        ]

        add_step("detect_fields", "ok" if username_field and password_field else "warning",
                 f"Username: {username_field or 'NOT FOUND'}, Password: {password_field or 'NOT FOUND'}",
                 {"visible_inputs": visible_inputs, "username_field": username_field, "password_field": password_field})

        # Step: Try HTTP login
        http_result = None
        if strategy in ("auto", "http_only"):
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False), timeout=timeout, headers=get_realistic_headers()) as session:
                http_result = await http_form_login(
                    session, login_url, username, password,
                    auth_config.get("username_selector", ""),
                    auth_config.get("password_selector", ""),
                    auth_config.get("submit_selector", ""),
                )
            if http_result.get("success"):
                add_step("http_login", "ok", f"HTTP login succeeded! Method: http, Final URL: {http_result.get('final_url', '')}")
                return {"steps": steps, "success": True, "result": http_result}
            else:
                add_step("http_login", "failed", f"HTTP login failed: {http_result.get('error', '')}")

        # Step: Try Playwright login
        pw_result = None
        if strategy in ("auto", "playwright_only"):
            if _PLAYWRIGHT_AVAILABLE:
                add_step("playwright_init", "ok", "Playwright available, launching browser...")
                pw_result = await playwright_form_login(
                    login_url, username, password,
                    auth_config.get("username_selector", ""),
                    auth_config.get("password_selector", ""),
                    auth_config.get("submit_selector", ""),
                    domain=domain,
                )
                if pw_result.get("success"):
                    add_step("playwright_login", "ok", f"Playwright login succeeded! Final URL: {pw_result.get('final_url', '')}")
                    return {"steps": steps, "success": True, "result": pw_result}
                else:
                    add_step("playwright_login", "failed", f"Playwright login failed: {pw_result.get('error', '')}",
                             pw_result.get("detected_fields"))
            else:
                add_step("playwright_init", "warning", "Playwright not installed, browser fallback unavailable")

        add_step("final", "failed", "All login methods failed")
        return {"steps": steps, "success": False, "result": pw_result or http_result or {}}

    except Exception as e:
        add_step("error", "failed", str(e))
        return {"steps": steps, "success": False, "error": str(e)}


# ──────────────────────────────────────────────────────────────────────────────
# Auth coverage + stability helpers
# ──────────────────────────────────────────────────────────────────────────────

def compute_auth_coverage(public_urls: list[dict], private_urls: list[dict]) -> dict:
    """Compute auth coverage stats from scan results."""
    total = len(public_urls) + len(private_urls)
    sensitive_public = sum(1 for u in public_urls if is_sensitive_page(u.get("url", "")))
    sensitive_private = sum(1 for u in private_urls if is_sensitive_page(u.get("url", "")))

    return {
        "public_count": len(public_urls),
        "private_count": len(private_urls),
        "total_count": total,
        "coverage_pct": round(len(private_urls) / max(total, 1) * 100, 1),
        "sensitive_public": sensitive_public,
        "sensitive_private": sensitive_private,
        "sensitive_total": sensitive_public + sensitive_private,
    }
