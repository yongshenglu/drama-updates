"""Rendered-page fetching for platforms that only serve their lists to JS.

iQIYI and Mango TV return a small server shell to plain HTTP clients and
build the drama grid client-side, so those two need a real browser. Tencent
and Youku do not -- they ship data in their HTML/JSON, so they stay on the
plain ``http_get`` path.

Browser resolution order:
  1. ``BROWSER_PATH`` env var
  2. Chrome / Edge on Windows
  3. Chromium from a Playwright install (used on CI)
  4. ``chromium`` / ``google-chrome`` on PATH
"""
from __future__ import annotations

import glob
import os
import shutil
import socket
import tempfile
import time
from pathlib import Path
from typing import Optional

from .http import USER_AGENT

_WINDOWS_BROWSERS = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
)

_PATH_BROWSERS = ("chromium", "chromium-browser", "google-chrome", "chrome", "msedge")


def _playwright_chromium() -> Optional[str]:
    """Locate a Chromium binary installed by ``playwright install chromium``."""
    home = Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or ".")
    patterns = [
        home / ".cache" / "ms-playwright" / "chromium-*" / "chrome-linux" / "chrome",
        home / ".cache" / "ms-playwright" / "chromium-*" / "chrome-linux" / "headless_shell",
        home / "AppData" / "Local" / "ms-playwright" / "chromium-*" / "chrome-win" / "chrome.exe",
        Path("/ms-playwright") / "chromium-*" / "chrome-linux" / "chrome",
    ]
    for pat in patterns:
        hits = sorted(glob.glob(str(pat)), reverse=True)
        if hits and os.path.exists(hits[0]):
            return hits[0]
    return None


def find_browser() -> Optional[str]:
    env = os.environ.get("BROWSER_PATH")
    if env and os.path.exists(env):
        return env
    for p in _WINDOWS_BROWSERS:
        if os.path.exists(p):
            return p
    pw = _playwright_chromium()
    if pw:
        return pw
    for name in _PATH_BROWSERS:
        hit = shutil.which(name)
        if hit:
            return hit
    return None


_PAGE = None
_BROWSER_PATH: Optional[str] = None


class BrowserUnavailable(RuntimeError):
    pass


def _page(browser_path: str):
    from DrissionPage import ChromiumOptions, ChromiumPage

    # Reuse an already-running debug browser when one is listening. A live
    # session owns the port, so launching a second one makes the CDP handshake
    # 404. If nothing is listening the launch path takes over as usual.
    port = os.environ.get("BROWSER_PORT", "9611")
    if _debug_port_busy(port):
        co = ChromiumOptions()
        co.set_local_port(port)
        return ChromiumPage(co)

    co = ChromiumOptions()
    co.set_browser_path(browser_path)
    co.headless()
    co.set_argument("--no-sandbox")
    co.set_argument("--disable-gpu")
    co.set_argument("--disable-dev-shm-usage")
    co.set_argument("--window-size=1440,2400")
    co.set_argument("--lang=zh-CN")
    co.set_argument("--hide-scrollbars")
    co.set_user_agent(USER_AGENT)
    # Pin an uncommon debug port and a private profile: user Chrome never binds
    # one of these, and a leftover collector instance cannot poison a new run.
    co.set_local_port(port)
    co.set_user_data_path(str(Path(tempfile.gettempdir()) / "drama-collector-profile"))
    return ChromiumPage(co)


def _debug_port_busy(port: str) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=0.4):
            return True
    except OSError:
        return False


def _shared_page():
    """Reuse one headless browser across collectors in this process."""
    global _PAGE, _BROWSER_PATH
    if _PAGE is not None and _PAGE.browser:
        return _PAGE
    browser_path = find_browser()
    if not browser_path:
        raise BrowserUnavailable(
            "no Chrome/Edge/Chromium found; set BROWSER_PATH or install one")
    _BROWSER_PATH = browser_path
    _PAGE = _page(browser_path)
    return _PAGE


def http_get_rendered(url: str, referer: str = "", settle: int = 8,
                      scrolls: int = 0, timeout: int = 60) -> str:
    """Load ``url`` in a headless browser and return the rendered HTML."""
    page = _shared_page()
    try:
        # Seed the origin with a plain visit so the channel page's Referer and
        # first-party cookies look like a normal in-site navigation.
        if referer:
            try:
                page.get(referer, timeout=timeout)
                time.sleep(2)
            except Exception:
                pass
        page.get(url, timeout=timeout)
        time.sleep(settle)
        for _ in range(scrolls):
            page.run_js("window.scrollBy(0, 1400);")
            time.sleep(1.5)
        return page.html
    except Exception:
        # Drop a broken browser so the next call starts clean.
        close_browser()
        raise


def close_browser() -> None:
    global _PAGE
    if _PAGE is not None:
        try:
            _PAGE.quit()
        except Exception:
            pass
        _PAGE = None
