#!/usr/bin/env python3
"""
ATV Avrupa Token Resolver (Playwright)
- rendert die Live-Seite wie ein echter Browser
- extrahiert die signierte CDN-M3U8 aus Netzwerk/DOM
- schreibt genau diese URL in output/atv.m3u8

Ergebnis:
#EXTM3U
https://trkvz-live.ercdn.net/atvavrupa/atvavrupa.m3u8?st=...&e=...
"""

import os
import re
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

OUTPUT = Path("output/atv.m3u8")
PAGE_URL = "https://www.atvavrupa.tv/canli-yayin"

TOKEN_RE = re.compile(
    r"https://trkvz-live\.ercdn\.net/atvavrupa/atvavrupa\.m3u8\?st=[^\"'&\s]+&e=\d+",
    re.I,
)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def save(url: str) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix(".m3u8.tmp")
    tmp.write_text(f"#EXTM3U\n{url}\n", encoding="utf-8")
    os.replace(tmp, OUTPUT)


def extract_with_playwright() -> str | None:
    found = None

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        context = browser.new_context(
            user_agent=UA,
            viewport={"width": 1366, "height": 768},
            locale="de-DE",
        )

        page = context.new_page()

        def handle_response(resp):
            nonlocal found
            url = resp.url
            if found:
                return
            m = TOKEN_RE.search(url)
            if m:
                found = m.group(0)

        page.on("response", handle_response)

        try:
            page.goto(PAGE_URL, wait_until="networkidle", timeout=30000)
        except PlaywrightTimeoutError:
            pass

        # DOM / JS durchsuchen
        if not found:
            html = page.content()
            m = TOKEN_RE.search(html)
            if m:
                found = m.group(0)

        if not found:
            for script in page.locator("script").all():
                try:
                    txt = script.inner_text()
                except Exception:
                    continue
                m = TOKEN_RE.search(txt)
                if m:
                    found = m.group(0)
                    break

        browser.close()

    return found


def main() -> int:
    try:
        url = extract_with_playwright()
        if not url:
            print("❌ Keine signierte Stream-URL gefunden")
            return 3

        save(url)
        print(f"💾 gespeichert: {OUTPUT}")
        print(url)
        return 0

    except Exception as e:
        print(f"❌ Fehler: {type(e).__name__}: {e}")
        return 99


if __name__ == "__main__":
    raise SystemExit(main())
