#!/usr/bin/env python3
"""
ATV Avrupa Token Resolver
- lädt die ATV Avrupa Live-Seite
- extrahiert den aktuellen signierten CDN-Link
- speichert nur die frische signierte URL als M3U8
"""

import os
import re
import html
import time
import requests

OUTPUT = "output/atv.m3u8"
PAGE_URL = "https://www.atvavrupa.tv/canli-yayin"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.atvavrupa.tv/",
    "Connection": "keep-alive",
}

TOKEN_PATTERN = re.compile(
    r'https?:\/\/trkvz-live\.ercdn\.net\/atvavrupa\/atvavrupa\.m3u8\?st=[^"\']+',
    re.I
)


def fetch_page(session: requests.Session) -> str:
    r = session.get(PAGE_URL, timeout=(5, 15))
    r.raise_for_status()
    return r.text


def extract_stream_url(page: str) -> str | None:
    source = html.unescape(page)
    match = TOKEN_PATTERN.search(source)
    return match.group(0).replace("\\/", "/") if match else None


def save_stream_url(url: str) -> None:
    os.makedirs("output", exist_ok=True)
    tmp = OUTPUT + ".tmp"

    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"#EXTM3U\n{url}\n")

    os.replace(tmp, OUTPUT)


def main() -> int:
    print("=== ATV Avrupa Token Resolver ===")
    start = time.time()

    try:
        session = requests.Session()
        session.headers.update(HEADERS)

        print("🌍 Lade Live-Seite …")
        page = fetch_page(session)

        stream_url = extract_stream_url(page)
        if not stream_url:
            raise ValueError("Keine signierte Stream-URL gefunden")

        print(f"🔗 Stream URL: {stream_url}")

        save_stream_url(stream_url)

        print(f"💾 gespeichert: {OUTPUT}")
        print(f"⏱️ Dauer: {round(time.time() - start, 2)}s")
        return 0

    except requests.HTTPError as e:
        print(f"❌ HTTP Fehler: {e}")
        return 1

    except requests.RequestException as e:
        print(f"❌ Netzwerkfehler: {e}")
        return 2

    except (OSError, ValueError) as e:
        print(f"❌ Fehler: {e}")
        return 3

    except Exception as e:
        print(f"❌ Unerwarteter Fehler: {type(e).__name__}: {e}")
        return 99


if __name__ == "__main__":
    raise SystemExit(main())
