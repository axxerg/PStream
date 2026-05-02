#!/usr/bin/env python3
"""
ATV Avrupa Resolver
- lädt die Live-Seite
- extrahiert die aktuelle signierte M3U8
- lädt die echte Playlist
- normalisiert relative URLs
- speichert fertige abspielbare M3U8
"""

import os
import re
import time
import html
import requests
from urllib.parse import urljoin

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

PATTERNS = [
    r'https?://[^\s"\']+\.m3u8[^\s"\']*',
    r'"(?:file|src|hls|streamUrl)"\s*:\s*"([^"]+\.m3u8[^"]*)"',
    r"'(?:file|src|hls|streamUrl)'\s*:\s*'([^']+\.m3u8[^']*)'",
    r'(https?:\\/\\/[^"\']+\.m3u8[^"\']*)',
]


def fetch_page(session: requests.Session) -> str:
    r = session.get(PAGE_URL, timeout=(5, 15))
    r.raise_for_status()
    return r.text


def extract_m3u8(html_text: str) -> str | None:
    source = html.unescape(html_text)

    for pattern in PATTERNS:
        match = re.search(pattern, source, re.IGNORECASE)
        if match:
            url = match.group(1) if match.lastindex else match.group(0)
            return url.replace("\\/", "/")

    return None


def normalize_playlist(content: str, playlist_url: str) -> str:
    """
    Convert relative URLs inside M3U8 to absolute URLs.
    """
    lines = []
    base = playlist_url.rsplit("/", 1)[0] + "/"

    for line in content.splitlines():
        stripped = line.strip()

        if stripped and not stripped.startswith("#"):
            line = urljoin(base, stripped)

        lines.append(line)

    return "\n".join(lines) + "\n"


def fetch_playlist(session: requests.Session, url: str) -> str:
    headers = dict(HEADERS)
    headers.update({
        "Accept": "*/*",
        "Origin": "https://www.atvavrupa.tv",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "cross-site",
    })

    r = session.get(url, headers=headers, timeout=(5, 15))
    r.raise_for_status()

    if "#EXTM3U" not in r.text:
        raise ValueError("Keine gültige M3U8 erhalten")

    return normalize_playlist(r.text, r.url)


def save_playlist(content: str) -> None:
    os.makedirs("output", exist_ok=True)
    tmp = OUTPUT + ".tmp"

    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)

    os.replace(tmp, OUTPUT)


def main() -> int:
    print("=== ATV Avrupa Resolver ===")
    start = time.time()

    try:
        session = requests.Session()
        session.headers.update(HEADERS)

        print("🌍 Lade Live-Seite …")
        page = fetch_page(session)

        stream_url = extract_m3u8(page)
        if not stream_url:
            raise ValueError("Keine Stream-URL im HTML gefunden")

        print(f"🔗 Stream URL: {stream_url}")

        playlist = fetch_playlist(session, stream_url)
        save_playlist(playlist)

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
