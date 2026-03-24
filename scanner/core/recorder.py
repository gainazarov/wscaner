"""
Recorder Engine — Record user login actions via headful Playwright browser.

Architecture:
  1. Start Xvfb virtual display + x11vnc + noVNC (websockify)
  2. Launch Playwright Chromium (headful) on the virtual display
  3. Navigate to target URL
  4. Inject JS event listeners to capture: click, type, navigation, submit
  5. User interacts via noVNC in the browser (streamed to frontend iframe)
  6. Events collected with smart selector generation & credential masking
  7. On stop: close browser, kill VNC, return recorded steps

Session Management:
  - One recording session at a time (global lock)
  - Auto-timeout after 5 minutes
  - Steps stored in memory by session_id
"""

import asyncio
import logging
import os
import signal
import subprocess
import time
import uuid
from typing import Optional

logger = logging.getLogger("scanner.recorder")

try:
    from playwright.async_api import async_playwright, Page, BrowserContext, Browser
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    _PLAYWRIGHT_AVAILABLE = False

# ──────────────────────────────────────────────────────────────────────────────
# JS injection script for recording events
# ──────────────────────────────────────────────────────────────────────────────

RECORDER_JS = """
(function() {
  if (window.__recorderInjected) return;
  window.__recorderInjected = true;
  window.__recordedEvents = window.__recordedEvents || [];

  // ─── Selector generator ─────────────────────────────────────
  function generateSelector(el) {
    if (!el || el === document.body || el === document.documentElement) return 'body';

    // Priority 1: id
    if (el.id && /^[a-zA-Z][\\w-]*$/.test(el.id)) {
      return '#' + el.id;
    }

    // Priority 2: name attribute
    if (el.name && /^[a-zA-Z][\\w-]*$/.test(el.name)) {
      const tag = el.tagName.toLowerCase();
      const sel = tag + '[name="' + el.name + '"]';
      if (document.querySelectorAll(sel).length === 1) return sel;
    }

    // Priority 3: data-testid / data-test / data-cy
    for (const attr of ['data-testid', 'data-test', 'data-cy', 'data-qa']) {
      const val = el.getAttribute(attr);
      if (val) return '[' + attr + '="' + val + '"]';
    }

    // Priority 4: type + placeholder combo for inputs
    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
      const type = el.type || 'text';
      if (el.placeholder) {
        const sel = el.tagName.toLowerCase() + '[type="' + type + '"][placeholder="' + el.placeholder + '"]';
        if (document.querySelectorAll(sel).length === 1) return sel;
      }
      if (type === 'password') return 'input[type="password"]';
      if (type === 'email') return 'input[type="email"]';
      if (type === 'submit') return 'input[type="submit"]';
    }

    // Priority 5: aria-label
    if (el.getAttribute('aria-label')) {
      const sel = el.tagName.toLowerCase() + '[aria-label="' + el.getAttribute('aria-label') + '"]';
      if (document.querySelectorAll(sel).length === 1) return sel;
    }

    // Priority 6: button/a with text content
    if (el.tagName === 'BUTTON' || el.tagName === 'A') {
      const text = (el.textContent || '').trim();
      if (text && text.length < 50) {
        const sel = el.tagName.toLowerCase() + ':has-text("' + text.replace(/"/g, '\\\\"') + '")';
        return sel;
      }
    }

    // Priority 7: role attribute
    if (el.getAttribute('role')) {
      const sel = '[role="' + el.getAttribute('role') + '"]';
      if (document.querySelectorAll(sel).length === 1) return sel;
    }

    // Priority 8: class-based (first unique class)
    if (el.className && typeof el.className === 'string') {
      const classes = el.className.trim().split(/\\s+/).filter(c => c.length > 2 && !/^(\\d|js-|css-)/.test(c));
      for (const cls of classes.slice(0, 3)) {
        const sel = el.tagName.toLowerCase() + '.' + CSS.escape(cls);
        if (document.querySelectorAll(sel).length === 1) return sel;
      }
    }

    // Priority 9: nth-child path (fallback)
    const path = [];
    let current = el;
    while (current && current !== document.body) {
      let selector = current.tagName.toLowerCase();
      if (current.id) {
        selector = '#' + current.id;
        path.unshift(selector);
        break;
      }
      const parent = current.parentElement;
      if (parent) {
        const siblings = Array.from(parent.children).filter(c => c.tagName === current.tagName);
        if (siblings.length > 1) {
          const index = siblings.indexOf(current) + 1;
          selector += ':nth-child(' + index + ')';
        }
      }
      path.unshift(selector);
      current = parent;
    }
    return path.join(' > ');
  }

  // ─── Detect if field is sensitive ────────────────────────────
  function isSensitiveField(el) {
    if (!el) return { isPassword: false, isUsername: false };
    const type = (el.type || '').toLowerCase();
    const name = (el.name || '').toLowerCase();
    const id = (el.id || '').toLowerCase();
    const autocomplete = (el.getAttribute('autocomplete') || '').toLowerCase();
    const placeholder = (el.placeholder || '').toLowerCase();

    const isPassword = type === 'password'
      || name.includes('pass') || id.includes('pass')
      || autocomplete === 'current-password' || autocomplete === 'new-password';

    const isUsername = type === 'email'
      || name.includes('user') || name.includes('email') || name.includes('login')
      || id.includes('user') || id.includes('email') || id.includes('login')
      || autocomplete === 'username' || autocomplete === 'email'
      || placeholder.includes('email') || placeholder.includes('user');

    return { isPassword, isUsername };
  }

  // ─── Debounce for type events ────────────────────────────────
  let typeTimers = {};

  // ─── Track focused input for keyboard-level recording ────────
  let lastFocusedInput = null;
  let lastKnownValues = {};

  // ─── Click listener ──────────────────────────────────────────
  document.addEventListener('click', function(e) {
    const target = e.target;
    if (!target || target === document.body) return;

    // If clicking an input/textarea — track it but don't record click event
    if ((target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') &&
        ['text','email','password','tel','url','search','number',''].includes(target.type || 'text')) {
      lastFocusedInput = target;
      return;
    }

    const selector = generateSelector(target);
    window.__recordedEvents.push({
      action: 'click',
      selector: selector,
      timestamp: Date.now(),
      tag: target.tagName.toLowerCase(),
      text: (target.textContent || '').trim().substring(0, 100)
    });
    console.log('[Recorder] click:', selector);
  }, true);

  // ─── Focus tracking for inputs ───────────────────────────────
  document.addEventListener('focus', function(e) {
    const t = e.target;
    if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA')) {
      lastFocusedInput = t;
    }
  }, true);

  // ─── Record typing helper (shared by input, change, focusout, paste, keyup) ─
  function recordTyping(target) {
    if (!target) return;
    if (target.tagName !== 'INPUT' && target.tagName !== 'TEXTAREA') return;

    const selector = generateSelector(target);
    const value = target.value;
    if (!value && !target.getAttribute('value')) return; // Skip empty

    // Skip if value didn't change
    if (lastKnownValues[selector] === value) return;
    lastKnownValues[selector] = value;

    if (typeTimers[selector]) clearTimeout(typeTimers[selector]);

    typeTimers[selector] = setTimeout(function() {
      const sensitivity = isSensitiveField(target);
      let recordedValue = target.value || target.getAttribute('value') || '';

      if (sensitivity.isPassword) {
        recordedValue = '{{PASSWORD_INPUT}}';
      } else if (sensitivity.isUsername) {
        recordedValue = '{{USER_INPUT}}';
      }

      // Overwrite previous type events for same selector
      window.__recordedEvents = window.__recordedEvents.filter(
        ev => !(ev.action === 'type' && ev.selector === selector)
      );

      window.__recordedEvents.push({
        action: 'type',
        selector: selector,
        value: recordedValue,
        timestamp: Date.now()
      });

      console.log('[Recorder] type:', selector, '->', sensitivity.isPassword ? '***' : recordedValue);
    }, 500);
  }

  // ─── Input listener (debounced — records final value) ────────
  document.addEventListener('input', function(e) {
    recordTyping(e.target);
  }, true);

  // ─── Change listener for React/custom inputs + select/checkbox
  document.addEventListener('change', function(e) {
    const target = e.target;
    if (!target) return;

    // React/custom text inputs that skip 'input' event
    if (target.tagName === 'INPUT' && target.type !== 'checkbox' && target.type !== 'radio') {
      recordTyping(target);
    }
    if (target.tagName === 'TEXTAREA') {
      recordTyping(target);
    }

    // Select dropdowns
    if (target.tagName === 'SELECT') {
      window.__recordedEvents.push({
        action: 'select',
        selector: generateSelector(target),
        value: target.value,
        timestamp: Date.now()
      });
    }

    // Checkboxes
    if (target.tagName === 'INPUT' && target.type === 'checkbox') {
      window.__recordedEvents.push({
        action: 'check',
        selector: generateSelector(target),
        timestamp: Date.now()
      });
    }
  }, true);

  // ─── Focusout: capture value when user leaves field ──────────
  document.addEventListener('focusout', function(e) {
    const target = e.target;
    if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA')) {
      if (target.value) {
        recordTyping(target);
      }
    }
  }, true);

  // ─── Periodically poll focused input for value changes ───────
  // (handles React inputs that don't fire standard events at all)
  let lastPollValue = '';
  let pollInterval = setInterval(function() {
    const el = document.activeElement;
    if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA')) {
      const val = el.value || '';
      if (val && val !== lastPollValue) {
        lastPollValue = val;
        recordTyping(el);
      }
    }
  }, 300);

  // ─── Submit listener ─────────────────────────────────────────
  document.addEventListener('submit', function(e) {
    const form = e.target;
    if (!form) return;

    const submitBtn = form.querySelector('button[type="submit"], input[type="submit"], button:not([type])');
    if (submitBtn) {
      const selector = generateSelector(submitBtn);
      const recent = window.__recordedEvents.slice(-3);
      const alreadyRecorded = recent.some(ev => ev.action === 'click' && ev.selector === selector);

      if (!alreadyRecorded) {
        window.__recordedEvents.push({
          action: 'click',
          selector: selector,
          timestamp: Date.now(),
          tag: submitBtn.tagName.toLowerCase(),
          text: (submitBtn.textContent || '').trim().substring(0, 100)
        });
        console.log('[Recorder] submit click:', selector);
      }
    }
  }, true);

  // ─── Keyboard listener (Enter key) ──────────────────────────
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') {
      const target = e.target;
      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA')) {
        window.__recordedEvents.push({
          action: 'press',
          selector: generateSelector(target),
          value: 'Enter',
          timestamp: Date.now()
        });
        console.log('[Recorder] press Enter on:', generateSelector(target));
      }
    }
  }, true);

  // ─── Keyup listener: capture value after each keystroke ──────
  document.addEventListener('keyup', function(e) {
    const target = e.target;
    if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA')) {
      if (target.value) {
        recordTyping(target);
      }
    }
  }, true);

  // ─── Paste listener: capture pasted content ──────────────────
  document.addEventListener('paste', function(e) {
    const target = e.target || document.activeElement;
    if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA')) {
      // Delay to let browser update the input value
      setTimeout(function() {
        if (target.value) {
          recordTyping(target);
          console.log('[Recorder] paste detected on:', generateSelector(target));
        }
      }, 100);
    }
  }, true);

  // ─── MutationObserver: detect React value changes via DOM ────
  // React uses Object.getOwnPropertyDescriptor to set .value without
  // firing input events. We intercept the value setter.
  function hookInputValueSetter(input) {
    if (input.__recorderHooked) return;
    input.__recorderHooked = true;

    const descriptor = Object.getOwnPropertyDescriptor(
      Object.getPrototypeOf(input), 'value'
    );
    if (descriptor && descriptor.set) {
      const originalSet = descriptor.set;
      Object.defineProperty(input, 'value', {
        set: function(val) {
          originalSet.call(this, val);
          // Debounced record
          recordTyping(this);
        },
        get: function() {
          return descriptor.get.call(this);
        },
        configurable: true
      });
    }
  }

  // Hook all existing inputs
  document.querySelectorAll('input, textarea').forEach(hookInputValueSetter);

  // Watch for new inputs added to DOM
  const observer = new MutationObserver(function(mutations) {
    for (const mutation of mutations) {
      for (const node of mutation.addedNodes) {
        if (node.nodeType !== 1) continue;
        if (node.tagName === 'INPUT' || node.tagName === 'TEXTAREA') {
          hookInputValueSetter(node);
        }
        if (node.querySelectorAll) {
          node.querySelectorAll('input, textarea').forEach(hookInputValueSetter);
        }
      }
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });

  console.log('[Recorder] Event listeners injected successfully (v2 — React/SPA support)');
})();
"""


# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

XVFB_DISPLAY = ":99"
XVFB_RESOLUTION = "1920x1080x24"
VNC_PORT = 5900
NOVNC_PORT = 6080
RECORDING_TIMEOUT = 600  # 10 minutes max


# ──────────────────────────────────────────────────────────────────────────────
# Global recording session state
# ──────────────────────────────────────────────────────────────────────────────

class RecorderSession:
    """Holds the state for one active recording session."""

    def __init__(self, session_id: str, domain: str):
        self.session_id = session_id
        self.domain = domain
        self.steps: list[dict] = []
        self.started_at = time.time()
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright_instance = None
        self._xvfb_proc: Optional[subprocess.Popen] = None
        self._fluxbox_proc: Optional[subprocess.Popen] = None
        self._vnc_proc: Optional[subprocess.Popen] = None
        self._novnc_proc: Optional[subprocess.Popen] = None
        self._navigations: list[str] = []
        self._auto_timeout_task: Optional[asyncio.Task] = None
        self.status = "starting"  # starting | recording | stopping | stopped
        self.error: Optional[str] = None

    @property
    def elapsed(self) -> float:
        return time.time() - self.started_at


# Single global session (one recording at a time)
_active_session: Optional[RecorderSession] = None
_session_lock = asyncio.Lock()


# ──────────────────────────────────────────────────────────────────────────────
# Process helpers
# ──────────────────────────────────────────────────────────────────────────────

def _kill_proc(proc: Optional[subprocess.Popen], name: str = ""):
    """Gracefully terminate a single subprocess."""
    if not proc:
        return
    try:
        if proc.poll() is None:
            os.kill(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.kill(proc.pid, signal.SIGKILL)
                proc.wait(timeout=2)
            logger.info(f"Stopped {name} (pid={proc.pid})")
    except (ProcessLookupError, OSError):
        pass
    except Exception as e:
        logger.warning(f"Error killing {name}: {e}")


def _kill_by_name(name: str):
    """Kill all processes matching a name pattern using /proc filesystem."""
    my_pid = os.getpid()
    try:
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            pid = int(entry)
            if pid == my_pid or pid == 1:
                continue
            try:
                with open(f"/proc/{pid}/cmdline", "rb") as f:
                    cmdline = f.read().decode("utf-8", errors="ignore")
                if name.lower() in cmdline.lower():
                    os.kill(pid, signal.SIGKILL)
                    logger.info(f"Killed process {pid} matching '{name}'")
            except (ProcessLookupError, FileNotFoundError, PermissionError):
                pass
    except Exception as e:
        logger.warning(f"_kill_by_name('{name}'): {e}")


def _nuke_all_display_procs():
    """Kill ALL Xvfb/VNC/fluxbox/websockify/chrome processes. Hard cleanup."""
    for name in ("Xvfb", "x11vnc", "fluxbox", "websockify", "chrome"):
        _kill_by_name(name)
    # Remove stale X lock & socket files
    for f in [
        f"/tmp/.X{XVFB_DISPLAY.replace(':', '')}-lock",
        f"/tmp/.X11-unix/X{XVFB_DISPLAY.replace(':', '')}",
    ]:
        try:
            if os.path.exists(f):
                os.remove(f)
        except OSError:
            pass


# ──────────────────────────────────────────────────────────────────────────────
# Xvfb + VNC + noVNC management
# ──────────────────────────────────────────────────────────────────────────────

def _start_xvfb() -> Optional[subprocess.Popen]:
    """Start Xvfb virtual display at 1920x1080."""
    try:
        proc = subprocess.Popen(
            [
                "Xvfb", XVFB_DISPLAY,
                "-screen", "0", XVFB_RESOLUTION,
                "-ac",
                "-nolisten", "tcp",
                "+extension", "RANDR",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        os.environ["DISPLAY"] = XVFB_DISPLAY
        time.sleep(0.8)
        if proc.poll() is not None:
            logger.error("Xvfb died immediately")
            return None
        logger.info(f"Xvfb started on {XVFB_DISPLAY} @ {XVFB_RESOLUTION} (pid={proc.pid})")
        return proc
    except Exception as e:
        logger.error(f"Failed to start Xvfb: {e}")
        return None


def _start_fluxbox() -> Optional[subprocess.Popen]:
    """Start fluxbox window manager with no decorations."""
    try:
        env = os.environ.copy()
        env["DISPLAY"] = XVFB_DISPLAY

        # Write fluxbox apps config: no decorations, maximize all windows
        fluxbox_dir = os.path.expanduser("~/.fluxbox")
        os.makedirs(fluxbox_dir, exist_ok=True)

        # apps file: remove decorations and maximize all windows
        with open(os.path.join(fluxbox_dir, "apps"), "w") as f:
            f.write("[app] (.*)\n  [Maximized]\t{yes}\n  [Deco]\t{NONE}\n[end]\n")

        # init file: hide toolbar, disable decorations globally
        with open(os.path.join(fluxbox_dir, "init"), "w") as f:
            f.write("session.screen0.toolbar.visible: false\n")
            f.write("session.screen0.defaultDeco: NONE\n")
            f.write("session.screen0.maxDisableMove: true\n")
            f.write("session.screen0.maxDisableResize: true\n")
            f.write("session.screen0.workspaces: 1\n")
            f.write("session.screen0.toolbar.widthPercent: 0\n")

        proc = subprocess.Popen(
            ["fluxbox"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        time.sleep(0.5)
        if proc.poll() is not None:
            return None
        logger.info(f"Fluxbox started (pid={proc.pid})")
        return proc
    except Exception as e:
        logger.warning(f"Fluxbox start failed (non-critical): {e}")
        return None


def _start_vnc() -> Optional[subprocess.Popen]:
    """Start x11vnc to serve the Xvfb display."""
    try:
        proc = subprocess.Popen(
            [
                "x11vnc",
                "-display", XVFB_DISPLAY,
                "-rfbport", str(VNC_PORT),
                "-nopw",
                "-forever",
                "-shared",
                "-noxdamage",
                "-cursor", "arrow",
                "-nowf",
                "-noxfixes",
                "-xkb",
                "-nomodtweak",
                "-repeat",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.5)
        if proc.poll() is not None:
            logger.error("x11vnc died immediately")
            return None
        logger.info(f"x11vnc started on port {VNC_PORT} (pid={proc.pid})")
        return proc
    except Exception as e:
        logger.error(f"Failed to start x11vnc: {e}")
        return None


def _start_novnc() -> Optional[subprocess.Popen]:
    """Start noVNC websockify to proxy VNC over WebSocket."""
    try:
        novnc_path = "/opt/noVNC"
        proc = subprocess.Popen(
            [
                "websockify",
                "--web", novnc_path,
                str(NOVNC_PORT),
                f"localhost:{VNC_PORT}",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.5)
        if proc.poll() is not None:
            logger.error("websockify (noVNC) died immediately")
            return None
        logger.info(f"noVNC started on port {NOVNC_PORT} -> VNC {VNC_PORT} (pid={proc.pid})")
        return proc
    except Exception as e:
        logger.error(f"Failed to start noVNC: {e}")
        return None


def _maximize_browser_window():
    """Use xdotool to find and maximize the Chromium window to fill the display."""
    env = os.environ.copy()
    env["DISPLAY"] = XVFB_DISPLAY
    max_attempts = 10
    for attempt in range(max_attempts):
        try:
            # Search for chromium/chrome windows
            result = subprocess.run(
                ["xdotool", "search", "--onlyvisible", "--class", "chromium"],
                capture_output=True, text=True, env=env, timeout=3,
            )
            window_ids = result.stdout.strip().split("\n")
            window_ids = [w for w in window_ids if w.strip()]

            if window_ids:
                for wid in window_ids:
                    # Remove decorations and maximize
                    subprocess.run(
                        ["xdotool", "windowactivate", "--sync", wid],
                        env=env, timeout=3, capture_output=True,
                    )
                    # Move and resize to fill the entire screen
                    subprocess.run(
                        ["xdotool", "windowmove", wid, "0", "0"],
                        env=env, timeout=3, capture_output=True,
                    )
                    subprocess.run(
                        ["xdotool", "windowsize", wid, "1920", "1080"],
                        env=env, timeout=3, capture_output=True,
                    )
                    # Also try wmctrl-style maximize via key
                    subprocess.run(
                        ["xdotool", "key", "--window", wid, "super+Up"],
                        env=env, timeout=3, capture_output=True,
                    )
                logger.info(f"Maximized {len(window_ids)} browser window(s) via xdotool")
                return True
        except Exception as e:
            if attempt == max_attempts - 1:
                logger.warning(f"xdotool maximize failed after {max_attempts} attempts: {e}")
        time.sleep(0.5)
    return False


# ──────────────────────────────────────────────────────────────────────────────
# Recorder API
# ──────────────────────────────────────────────────────────────────────────────

async def start_recording(domain: str, start_url: str = "") -> dict:
    """
    Start a recording session.

    Returns: { success, session_id, status, novnc_url, ... }
    """
    global _active_session

    if not _PLAYWRIGHT_AVAILABLE:
        return {"success": False, "error": "Playwright not installed"}

    async with _session_lock:
        # Force-cleanup any stale/stuck session
        if _active_session:
            old = _active_session
            logger.warning(f"Force-cleaning previous session {old.session_id} (status={old.status})")
            try:
                if old._auto_timeout_task and not old._auto_timeout_task.done():
                    old._auto_timeout_task.cancel()
                await _cleanup_session(old)
            except Exception:
                pass
            _active_session = None

        session_id = f"rec_{uuid.uuid4().hex[:12]}"
        session = RecorderSession(session_id, domain)
        _active_session = session

    try:
        # Nuke all leftover processes from previous sessions
        _nuke_all_display_procs()
        await asyncio.sleep(0.5)

        # Step 1: Xvfb
        logger.info(f"[{session_id}] Starting Xvfb ({XVFB_RESOLUTION})...")
        session._xvfb_proc = _start_xvfb()
        if not session._xvfb_proc:
            raise RuntimeError("Failed to start Xvfb")

        # Step 2: Fluxbox WM (so maximize works)
        session._fluxbox_proc = _start_fluxbox()

        # Step 3: x11vnc
        logger.info(f"[{session_id}] Starting VNC...")
        session._vnc_proc = _start_vnc()
        if not session._vnc_proc:
            raise RuntimeError("Failed to start VNC")

        # Step 4: noVNC websockify
        logger.info(f"[{session_id}] Starting noVNC...")
        session._novnc_proc = _start_novnc()
        if not session._novnc_proc:
            raise RuntimeError("Failed to start noVNC")

        # Step 5: Playwright browser (headful on Xvfb)
        logger.info(f"[{session_id}] Launching Playwright browser (headful, 1920x1080)...")
        pw = await async_playwright().start()
        session.playwright_instance = pw

        browser = await pw.chromium.launch(
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-software-rasterizer",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-extensions",
                "--no-first-run",
                "--no-default-browser-check",
                # Fill the entire Xvfb display
                "--window-position=0,0",
                "--window-size=1920,1080",
                "--start-maximized",
                # Use kiosk mode: full-screen, no chrome (address bar, tabs, etc.)
                "--kiosk",
            ],
        )
        session.browser = browser

        # Use no_viewport so browser content auto-fills the window size
        context = await browser.new_context(
            no_viewport=True,
            locale="en-US",
            timezone_id="America/New_York",
        )
        session.context = context

        page = await context.new_page()
        session.page = page

        # Anti-detection
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            delete navigator.__proto__.webdriver;
        """)

        # Step 6: Navigate to target
        target_url = start_url or f"https://{domain}"
        logger.info(f"[{session_id}] Navigating to {target_url}")

        session.steps.append({
            "action": "goto",
            "value": target_url,
            "timestamp": time.time(),
            "description": "Navigate to starting page",
        })

        try:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            logger.warning(f"[{session_id}] Navigation warning (continuing): {e}")

        await asyncio.sleep(1)

        # Step 6.5: Force maximize browser window via xdotool
        _maximize_browser_window()

        # Step 7: Inject recording JS
        await _inject_recorder(page)

        # Listen for navigations to re-inject JS
        page.on("framenavigated", lambda frame: asyncio.ensure_future(
            _on_navigation(session, frame)
        ))

        session.status = "recording"
        logger.info(f"[{session_id}] Recording started for {domain}")

        # Step 8: Auto-timeout
        session._auto_timeout_task = asyncio.create_task(_auto_timeout(session))

        return {
            "success": True,
            "session_id": session_id,
            "status": "recording",
            "novnc_url": f"http://localhost:{NOVNC_PORT}/vnc.html?autoconnect=true&resize=remote&reconnect=true&reconnect_delay=1000&show_dot=true&view_only=false",
            "domain": domain,
            "start_url": target_url,
        }

    except Exception as e:
        logger.exception(f"[{session_id}] Failed to start recording: {e}")
        await _cleanup_session(session)
        async with _session_lock:
            _active_session = None
        return {"success": False, "error": str(e)}


async def stop_recording(session_id: str) -> dict:
    """
    Stop a recording session and return recorded steps.

    Returns: { success, steps, session_id, ... }
    """
    global _active_session

    async with _session_lock:
        session = _active_session
        if not session or session.session_id != session_id:
            # Clean up stale session if it exists
            if _active_session and _active_session.status in ("stopping", "stopped"):
                try:
                    await _cleanup_session(_active_session)
                except Exception:
                    pass
                _active_session = None
            return {"success": False, "error": f"Session {session_id} not found"}

        if session.status == "stopped":
            _active_session = None
            return {"success": False, "error": "Session already stopped"}

        session.status = "stopping"

    # Cancel auto-timeout task (don't wait — it might be the caller)
    if session._auto_timeout_task and not session._auto_timeout_task.done():
        session._auto_timeout_task.cancel()

    # Collect events from browser
    browser_events = []
    if session.page:
        try:
            raw = await asyncio.wait_for(
                session.page.evaluate("window.__recordedEvents || []"),
                timeout=5.0,
            )
            if isinstance(raw, list):
                browser_events = raw
            logger.info(f"[{session_id}] Collected {len(browser_events)} events")
        except asyncio.TimeoutError:
            logger.warning(f"[{session_id}] Timed out collecting events")
        except Exception as e:
            logger.warning(f"[{session_id}] Failed to collect events: {e}")

    # Merge steps
    try:
        merged = _merge_and_clean_steps(session.steps, browser_events, session._navigations)
    except Exception as e:
        logger.warning(f"[{session_id}] Error merging steps: {e}")
        merged = session.steps

    duration = session.elapsed
    logger.info(f"[{session_id}] Final steps: {len(merged)}")

    # Cleanup everything
    await _cleanup_session(session)
    session.status = "stopped"

    async with _session_lock:
        _active_session = None

    logger.info(f"[{session_id}] Recording stopped ({len(merged)} steps, {duration:.1f}s)")

    return {
        "success": True,
        "session_id": session_id,
        "steps": merged,
        "total_steps": len(merged),
        "duration": duration,
    }


async def get_recording_status(session_id: str = "") -> dict:
    """Get the current recording session status and live events count."""
    global _active_session

    if not _active_session:
        return {"active": False, "status": "idle"}

    session = _active_session
    if session_id and session.session_id != session_id:
        return {"active": False, "status": "idle", "error": "Session mismatch"}

    # Detect stale sessions stuck in stopping for too long
    if session.status in ("stopping", "stopped") and session.elapsed > RECORDING_TIMEOUT + 30:
        logger.warning(f"[{session.session_id}] Stale session, force cleanup")
        try:
            await _cleanup_session(session)
        except Exception:
            pass
        async with _session_lock:
            _active_session = None
        return {"active": False, "status": "idle"}

    result = {
        "active": session.status in ("starting", "recording"),
        "session_id": session.session_id,
        "status": session.status,
        "domain": session.domain,
        "elapsed": int(session.elapsed),
        "timeout": RECORDING_TIMEOUT,
    }

    # Get live event count from browser
    if session.status == "recording" and session.page:
        try:
            count = await asyncio.wait_for(
                session.page.evaluate("(window.__recordedEvents || []).length"),
                timeout=3.0,
            )
            result["events_count"] = count
        except (asyncio.TimeoutError, Exception):
            result["events_count"] = 0

    return result


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

async def _inject_recorder(page: Page):
    """Inject the recording JS into the page and all its frames."""
    try:
        await page.evaluate(RECORDER_JS)
        logger.info("Recorder JS injected into main page")
    except Exception as e:
        logger.warning(f"Failed to inject recorder JS: {e}")

    for frame in page.frames:
        if frame != page.main_frame:
            try:
                await frame.evaluate(RECORDER_JS)
            except Exception:
                pass


async def _on_navigation(session: RecorderSession, frame):
    """Handle page navigation — re-inject JS and record it."""
    if session.status != "recording":
        return
    try:
        page = session.page
        if not page:
            return
        url = frame.url
        if frame == page.main_frame and url and url != "about:blank":
            # Avoid duplicate goto
            if session.steps:
                last = session.steps[-1]
                if last.get("action") == "goto" and last.get("value") == url:
                    return
            session._navigations.append(url)
            logger.info(f"[{session.session_id}] Navigation: {url}")
            await asyncio.sleep(1)
            await _inject_recorder(page)
    except Exception as e:
        logger.warning(f"[{session.session_id}] Navigation handler error: {e}")


async def _auto_timeout(session: RecorderSession):
    """Auto-stop recording after timeout. Runs as a background asyncio task."""
    global _active_session
    try:
        await asyncio.sleep(RECORDING_TIMEOUT)
        if session.status != "recording":
            return
        logger.warning(f"[{session.session_id}] Auto-timeout after {RECORDING_TIMEOUT}s")

        # Direct cleanup instead of calling stop_recording (avoids lock deadlock)
        session.status = "stopping"

        # Try to collect events
        if session.page:
            try:
                await asyncio.wait_for(
                    session.page.evaluate("window.__recordedEvents || []"),
                    timeout=3.0,
                )
            except Exception:
                pass

        await _cleanup_session(session)
        session.status = "stopped"

        async with _session_lock:
            if _active_session and _active_session.session_id == session.session_id:
                _active_session = None

        logger.info(f"[{session.session_id}] Auto-timeout cleanup complete")

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.exception(f"Auto-timeout error: {e}")
        session.status = "stopped"
        try:
            await _cleanup_session(session)
            async with _session_lock:
                if _active_session and _active_session.session_id == session.session_id:
                    _active_session = None
        except Exception:
            pass


async def _cleanup_session(session: RecorderSession):
    """Clean up all resources for a session."""
    # Close browser
    if session.browser:
        try:
            await asyncio.wait_for(session.browser.close(), timeout=5.0)
        except Exception as e:
            logger.warning(f"Error closing browser: {e}")
        session.browser = None
        session.context = None
        session.page = None

    # Stop playwright
    if session.playwright_instance:
        try:
            await asyncio.wait_for(
                session.playwright_instance.stop(),
                timeout=5.0,
            )
        except Exception as e:
            logger.warning(f"Error stopping playwright: {e}")
        session.playwright_instance = None

    # Kill spawned processes
    _kill_proc(session._novnc_proc, "noVNC")
    _kill_proc(session._vnc_proc, "x11vnc")
    _kill_proc(session._fluxbox_proc, "fluxbox")
    _kill_proc(session._xvfb_proc, "Xvfb")

    session._novnc_proc = None
    session._vnc_proc = None
    session._fluxbox_proc = None
    session._xvfb_proc = None

    # Nuclear cleanup — kill anything still lingering
    _kill_by_name("chrome")
    _kill_by_name("fluxbox")

    logger.info(f"[{session.session_id}] Cleanup complete")


def _merge_and_clean_steps(
    initial_steps: list[dict],
    browser_events: list[dict],
    navigations: list[str],
) -> list[dict]:
    """Merge initial goto + browser events, add smart waits, generate descriptions."""
    steps = []

    # Initial goto
    if initial_steps:
        first = initial_steps[0]
        steps.append({
            "action": first.get("action", "goto"),
            "value": first.get("value", ""),
            "description": first.get("description", "Navigate to starting page"),
        })

    sorted_events = sorted(browser_events, key=lambda e: e.get("timestamp", 0))
    prev_ts = sorted_events[0].get("timestamp", 0) if sorted_events else 0

    for event in sorted_events:
        action = event.get("action", "")
        ts = event.get("timestamp", 0)

        # Smart wait if gap > 1.5s
        if prev_ts and ts - prev_ts > 1500:
            wait_ms = min(int(ts - prev_ts), 5000)
            steps.append({
                "action": "wait",
                "wait_ms": wait_ms,
                "description": f"Wait {wait_ms}ms",
            })

        step = {"action": action}

        if action == "goto":
            step["value"] = event.get("url", event.get("value", ""))
            step["description"] = f"Navigate to {step['value']}"
        elif action == "click":
            step["selector"] = event.get("selector", "")
            text = event.get("text", "")
            tag = event.get("tag", "")
            step["description"] = f"Click {tag}: {text[:60]}" if text else f"Click {step['selector']}"
        elif action == "type":
            step["selector"] = event.get("selector", "")
            step["value"] = event.get("value", "")
            if "PASSWORD_INPUT" in step["value"]:
                step["description"] = "Type password"
            elif "USER_INPUT" in step["value"]:
                step["description"] = "Type username/email"
            else:
                step["description"] = f"Type: {step['value'][:40]}"
        elif action == "select":
            step["selector"] = event.get("selector", "")
            step["value"] = event.get("value", "")
            step["description"] = f"Select: {step['value']}"
        elif action == "check":
            step["selector"] = event.get("selector", "")
            step["description"] = f"Check: {step['selector']}"
        elif action == "press":
            step["selector"] = event.get("selector", "")
            step["value"] = event.get("value", "")
            step["description"] = f"Press {step['value']}"
        elif action == "wait":
            step["wait_ms"] = event.get("wait_ms", 1000)
            step["description"] = f"Wait {step['wait_ms']}ms"
        else:
            continue

        steps.append(step)
        prev_ts = ts

    # Final settle wait
    if len(steps) > 1:
        steps.append({
            "action": "wait",
            "wait_ms": 2000,
            "description": "Wait for page to settle after login",
        })

    return steps
