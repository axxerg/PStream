#!/usr/bin/env python3
"""
ATV Avrupa Fetcher
- probiert erst den direkten Turkuvaz-Feed
- fällt bei 403 automatisch auf einen funktionierenden Relay zurück
- normalisiert relative URLs
- speichert fertige abspielbare M3U8
"""

import os
import time
from urllib.parse import urljoin

import requests

OUTPUT = "output/atv.m3u8"

PRIMARY_URL = "https://trkvz-live.ercdn.net/atvavrupa/atvavrupa.m3u8"
FALLBACK_URL = "https://ythls-v3.onrender.com/channel/UCUVZ7T_kwkxDOGFcDlFI-hg.m3u8"

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

        playlist = None

        try:
            print(f"🔗 Primary: {PRIMARY_URL}")
            playlist = fetch_playlist(session, PRIMARY_URL)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 403:
                print("⚠️ Primary blocked (403), switching to fallback relay …")
                print(f"🔗 Fallback: {FALLBACK_URL}")
                playlist = fetch_playlist(session, FALLBACK_URL)
            else:
                raise

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
