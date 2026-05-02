import os
import re
import time
import requests

OUTPUT = "output/showturk.m3u8"
PAGE_URL = "https://www.showturk.com.tr/canli-yayin"

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
    "Referer": "https://www.showturk.com.tr/",
    "Connection": "keep-alive",
}

M3U8_RE = re.compile(r'https?://[^\s"\']+\.m3u8[^\s"\']*', re.IGNORECASE)


def fetch_page(session: requests.Session) -> str:
    """Load ShowTurk live page."""
    r = session.get(PAGE_URL, timeout=(5, 15))
    r.raise_for_status()
    return r.text


def extract_m3u8(html: str) -> str | None:
    """Extract first M3U8 URL from page source."""
    match = M3U8_RE.search(html)
    return match.group(0) if match else None


def fetch_playlist(session: requests.Session, url: str) -> str:
    """Fetch final M3U8 playlist."""
    headers = dict(HEADERS)
    headers.update({
        "Accept": "*/*",
        "Origin": "https://www.showturk.com.tr",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "cross-site",
    })

    r = session.get(url, headers=headers, timeout=(5, 15))
    r.raise_for_status()

    if "#EXTM3U" not in r.text:
        raise ValueError("Keine gültige M3U8 erhalten")

    return r.text


def save_playlist(content: str) -> None:
    os.makedirs("output", exist_ok=True)
    tmp = OUTPUT + ".tmp"

    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)

    os.replace(tmp, OUTPUT)


def main() -> int:
    print("=== ShowTurk Extractor ===")
    start = time.time()

    try:
        session = requests.Session()
        session.headers.update(HEADERS)

        print("🌍 Lade Live-Seite …")
        html = fetch_page(session)

        stream_url = extract_m3u8(html)
        if not stream_url:
            raise ValueError("Keine M3U8 URL im HTML gefunden")

        print(f"🔗 Stream URL gefunden: {stream_url}")

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
