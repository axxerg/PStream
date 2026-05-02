#!/usr/bin/env python3
"""
ATV Avrupa Fetcher
- probiert mehrere bekannte ATV-Quellen
- nimmt die erste funktionierende M3U8
- normalisiert relative URLs
- speichert fertige abspielbare Playlist
"""

import os
import time
from urllib.parse import urljoin

import requests

OUTPUT = "output/atv.m3u8"

STREAM_SOURCES = [
    "https://trkvz-live.ercdn.net/atvavrupa/atvavrupa.m3u8",
    "https://ythls-v3.onrender.com/channel/UCUVZ7T_kwkxDOGFcDlFI-hg.m3u8",
    "https://ythls.armelin.one/channel/UCUVZ7T_kwkxDOGFcDlFI-hg.m3u8",
    "https://koprulu.global.ssl.fastly.net/ythls?kanal_id=UCUVZ7T_kwkxDOGFcDlFI-hg&m3u8",
    "https://livestream.zazerconer.workers.dev/channel/UCUVZ7T_kwkxDOGFcDlFI-hg.m3u8",
    "https://new.cache-stream.workers.dev/stream/UCUVZ7T_kwkxDOGFcDlFI-hg/live.m3u8",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Referer": "https://www.atvavrupa.tv/",
    "Origin": "https://www.atvavrupa.tv",
    "Connection": "keep-alive",
}


def normalize_playlist(content: str, playlist_url: str) -> str:
    lines = []
    base = playlist_url.rsplit("/", 1)[0] + "/"

    for line in content.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            line = urljoin(base, stripped)
        lines.append(line)

    return "\n".join(lines) + "\n"


def fetch_playlist(session: requests.Session, url: str) -> str:
    r = session.get(url, timeout=(5, 15))
    r.raise_for_status()

    if "#EXTM3U" not in r.text:
        raise ValueError("Keine gültige M3U8 erhalten")

    return normalize_playlist(r.text, r.url)


def resolve_playlist(session: requests.Session) -> str:
    last_error = None

    for url in STREAM_SOURCES:
        try:
            print(f"🔗 Try: {url}")
            return fetch_playlist(session, url)
        except Exception as e:
            print(f"  ⚠️ Failed: {type(e).__name__}: {e}")
            last_error = e

    raise RuntimeError(f"Alle Quellen fehlgeschlagen: {last_error}")


def save_playlist(content: str) -> None:
    os.makedirs("output", exist_ok=True)
    tmp = OUTPUT + ".tmp"

    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)

    os.replace(tmp, OUTPUT)


def main() -> int:
    print("=== ATV Avrupa Fetcher ===")
    start = time.time()

    try:
        session = requests.Session()
        session.headers.update(HEADERS)

        playlist = resolve_playlist(session)
        save_playlist(playlist)

        print(f"💾 gespeichert: {OUTPUT}")
        print(f"⏱️ Dauer: {round(time.time() - start, 2)}s")
        return 0

    except Exception as e:
        print(f"❌ Fehler: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
