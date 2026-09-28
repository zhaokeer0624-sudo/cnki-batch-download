#!/usr/bin/env python3
"""
patch_cnki_mcp.py — make an installed `cnki-mcp` work reliably.

`cnki-mcp` (https://github.com/NoFixedPoint/cnki-mcp, MIT) drives CNKI
(中国知网) through Playwright. Installed as-is it fails in two ways, and this
script patches the installed module to fix both.

Patch 1 — headed browser with a persistent profile
    Upstream launches headless Chromium and calls `browser.new_page()` for every
    request. Playwright gives each `new_page()` its own browser context, so no
    session ever persists, and CNKI's block-puzzle captcha
    (`kns.cnki.net/verify/home?captchaType=blockPuzzle`) fires on the search page
    every single time. A headless browser cannot solve a slider captcha, so
    every tool call dies there.

    After patching, the browser runs visibly in a persistent
    `launch_persistent_context()` profile. You slide the captcha once and the
    session is remembered, so later calls go straight through.

    Two env vars control it (both defaulted, nothing to configure):
        CNKI_MCP_HEADLESS        default "false" (a visible window is required so
                                 a human can slide the captcha)
        CNKI_MCP_USER_DATA_DIR   default "~/.cnki-mcp/chrome-profile"

Patch 2 — reliable navigation
    All 11 `page.goto(...)` calls use Playwright's default `wait_until="load"`.
    CNKI article pages pull third-party resources that never finish, so the load
    event never fires and `goto()` raises `Timeout 30000ms exceeded`. That breaks
    `download_paper_pdf`, `get_paper_detail` and `get_paper_bibtex`.

    After patching they use `wait_until="domcontentloaded", timeout=60000`, plus
    a bounded wait for the PDF button (`a#pdfDown`), which DOM-ready can precede.

Usage
-----
    python patch_cnki_mcp.py                 # patch the installed copy
    python patch_cnki_mcp.py --check         # report status, change nothing
    python patch_cnki_mcp.py --restore       # restore the .orig backup
    python patch_cnki_mcp.py --target PATH   # patch a specific file

Run `--check` after any `pip install`/upgrade of cnki-mcp: a reinstall
overwrites the module and silently reverts both patches.

Note: `download_paper_pdf` still needs whatever access your CNKI account carries
(institutional or personal), and the browser window will appear on your desktop
during tool calls.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import py_compile
import re
import shutil
import sys

ORIG_SUFFIX = ".orig"

# --------------------------------------------------------------------------- #
# Patch 1 — headed + persistent browser profile
# --------------------------------------------------------------------------- #

HELPERS_ANCHOR = "paper_registry = PaperRegistry()\n"

HELPERS_BLOCK = '''
# =================== Local patch: persistent headed profile ===================

def _cfg_flag(name: str, default: bool) -> bool:
    """Read a boolean env var. Empty/unset -> default."""
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() not in ("0", "false", "no", "off")


def _profile_dir() -> str:
    """Persistent Chromium profile dir, so a solved captcha / session survives restarts."""
    path = os.environ.get("CNKI_MCP_USER_DATA_DIR")
    if not path:
        path = os.path.join(os.path.expanduser("~"), ".cnki-mcp", "chrome-profile")
    os.makedirs(path, exist_ok=True)
    return path
'''

POOL_OLD = '''class BrowserPool:
    """Manages a singleton Playwright browser with idle timeout."""

    IDLE_TIMEOUT = 600  # 10 min

    def __init__(self):
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._last_used: float = 0
        self._lock = asyncio.Lock()

    async def _create_browser(self) -> Browser:
        if self._playwright is None:
            self._playwright = await async_playwright().start()
        browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-infobars",
                "--disable-extensions",
                "--disable-gpu",
            ],
        )
        return browser

    async def _is_browser_alive(self) -> bool:
        if self._browser is None:
            return False
        try:
            return self._browser.is_connected()
        except Exception:
            return False

    async def get_page(self) -> Page:
        """Get a new page from the browser (caller must close it)."""
        async with self._lock:
            now = time.time()
            if self._browser is not None:
                if now - self._last_used > self.IDLE_TIMEOUT:
                    await self._close_internal()
                elif not await self._is_browser_alive():
                    self._browser = None
            if self._browser is None:
                self._browser = await self._create_browser()
            self._last_used = now

        page = await self._browser.new_page(
            user_agent=random.choice(USER_AGENTS),
        )
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        return page

    async def _close_internal(self):
        if self._browser is not None:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None

    async def close(self):
        async with self._lock:
            await self._close_internal()
        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None'''

POOL_NEW = '''class BrowserPool:
    """Singleton persistent Chromium profile (headed by default) with idle timeout.

    Patched: upstream used `chromium.launch(headless=True)` plus a fresh
    `new_page()` per call, which means a new browser context every time and
    therefore no session reuse — so CNKI's captcha had to be re-solved on every
    single call. A persistent user-data-dir in a visible window lets one manual
    solve stick.
    """

    IDLE_TIMEOUT = 600  # 10 min

    def __init__(self):
        self._playwright: Optional[Playwright] = None
        self._context = None
        self._last_used: float = 0
        self._lock = asyncio.Lock()

    async def _create_context(self):
        if self._playwright is None:
            self._playwright = await async_playwright().start()
        context = await self._playwright.chromium.launch_persistent_context(
            _profile_dir(),
            headless=_cfg_flag("CNKI_MCP_HEADLESS", False),
            viewport=None,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-infobars",
                "--disable-extensions",
                "--disable-gpu",
                "--start-maximized",
            ],
            user_agent=USER_AGENTS[0],
        )
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        return context

    async def _is_browser_alive(self) -> bool:
        if self._context is None:
            return False
        try:
            self._context.pages
            return True
        except Exception:
            return False

    async def get_page(self) -> Page:
        """Get a new page from the persistent profile (caller must close it)."""
        async with self._lock:
            now = time.time()
            if self._context is not None:
                if now - self._last_used > self.IDLE_TIMEOUT:
                    await self._close_internal()
                elif not await self._is_browser_alive():
                    self._context = None
            if self._context is None:
                self._context = await self._create_context()
            self._last_used = now

        return await self._context.new_page()

    async def _close_internal(self):
        if self._context is not None:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None

    async def close(self):
        async with self._lock:
            await self._close_internal()
        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None'''

# --------------------------------------------------------------------------- #
# Patch 2 — navigation that survives CNKI's never-finishing page loads
# --------------------------------------------------------------------------- #

# Matches `await page.goto(ARG)` where ARG contains no comma, i.e. a call that
# does NOT already pass wait_until/timeout.
GOTO_RE = re.compile(r"await page\.goto\((?P<arg>[^,)]+)\)")

GOTO_FIXED = 'await page.goto({arg}, wait_until="domcontentloaded", timeout=60000)'

BUTTON_OLD = """    # Find PDF download button
    pdf_btn = await page.query_selector("a#pdfDown")"""

BUTTON_NEW = """    # Find PDF download button (DOM-ready can precede the button, so wait briefly)
    try:
        await page.wait_for_selector("a#pdfDown", timeout=15000)
    except Exception:
        pass
    pdf_btn = await page.query_selector("a#pdfDown")"""


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def find_target(explicit: str | None) -> str:
    if explicit:
        if not os.path.isfile(explicit):
            sys.exit(f"error: no such file: {explicit}")
        return os.path.abspath(explicit)
    spec = importlib.util.find_spec("cnki_mcp_server")
    if spec is None or not spec.origin:
        sys.exit(
            "error: cnki_mcp_server is not importable.\n"
            "Install it first:  pip install git+https://github.com/NoFixedPoint/cnki-mcp.git"
        )
    return os.path.abspath(spec.origin)


def patch_1_done(src: str) -> bool:
    return "launch_persistent_context" in src and "_profile_dir" in src


def patch_2_done(src: str) -> bool:
    return not GOTO_RE.search(src) and 'wait_for_selector("a#pdfDown"' in src


def apply_patches(src: str) -> tuple[str, list[str]]:
    notes: list[str] = []

    # --- patch 1 ---
    if patch_1_done(src):
        notes.append("patch 1 (persistent headed profile): already applied")
    else:
        if HELPERS_ANCHOR not in src:
            notes.append("patch 1: SKIPPED — anchor `paper_registry = PaperRegistry()` not found")
        elif POOL_OLD not in src:
            notes.append("patch 1: SKIPPED — original BrowserPool not found verbatim")
        else:
            src = src.replace(HELPERS_ANCHOR, HELPERS_ANCHOR + HELPERS_BLOCK, 1)
            src = src.replace(POOL_OLD, POOL_NEW, 1)
            notes.append("patch 1 (persistent headed profile): APPLIED")

    # --- patch 2a: goto wait_until ---
    src, n_goto = GOTO_RE.subn(lambda m: GOTO_FIXED.format(arg=m.group("arg")), src)
    if n_goto:
        notes.append(f"patch 2a (goto wait_until): APPLIED to {n_goto} call(s)")
    else:
        notes.append("patch 2a (goto wait_until): already applied / nothing to do")

    # --- patch 2b: PDF button wait ---
    if 'wait_for_selector("a#pdfDown"' in src:
        notes.append("patch 2b (PDF button wait): already applied")
    elif BUTTON_OLD in src:
        src = src.replace(BUTTON_OLD, BUTTON_NEW, 1)
        notes.append("patch 2b (PDF button wait): APPLIED")
    else:
        notes.append("patch 2b (PDF button wait): SKIPPED — anchor not found")

    return src, notes


def main() -> int:
    ap = argparse.ArgumentParser(description="Patch an installed cnki-mcp.")
    ap.add_argument("--target", help="path to cnki_mcp_server.py (default: the installed one)")
    ap.add_argument("--check", action="store_true", help="report status only, change nothing")
    ap.add_argument("--restore", action="store_true", help="restore the .orig backup")
    args = ap.parse_args()

    target = find_target(args.target)
    backup = target + ORIG_SUFFIX
    print(f"target : {target}")

    if args.restore:
        if not os.path.isfile(backup):
            sys.exit(f"error: no backup at {backup}")
        shutil.copyfile(backup, target)
        print(f"restored from {backup}")
        return 0

    src = open(target, encoding="utf-8").read()

    if args.check:
        print(f"patch 1 (persistent headed profile): {'applied' if patch_1_done(src) else 'NOT applied'}")
        print(f"patch 2 (reliable navigation)      : {'applied' if patch_2_done(src) else 'NOT applied'}")
        print(f"backup : {'present' if os.path.isfile(backup) else 'missing'} ({backup})")
        return 0

    if patch_1_done(src) and patch_2_done(src):
        print("already fully patched — nothing to do")
        return 0

    if not os.path.isfile(backup):
        shutil.copyfile(target, backup)
        print(f"backup : {backup}")
    else:
        print(f"backup : {backup} (kept, not overwritten)")

    patched, notes = apply_patches(src)
    for line in notes:
        print("  -", line)

    if "SKIPPED" in " ".join(notes) and patched == src:
        print("nothing changed")
        return 1

    try:
        compile(patched, target, "exec")
    except SyntaxError as exc:
        print(f"error: patched source does not compile ({exc}); leaving file untouched")
        return 1

    open(target, "w", encoding="utf-8", newline="\n").write(patched)

    try:
        py_compile.compile(target, doraise=True)
    except py_compile.PyCompileError as exc:
        print(f"error: py_compile failed ({exc}); restoring backup")
        shutil.copyfile(backup, target)
        return 1

    print("wrote patched file — syntax OK")
    print("\nnext: restart your MCP client so it picks up the patched server.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
