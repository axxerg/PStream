import os
import time
import requests
from urllib.parse import urljoin

OUTPUT = "output/eurostar.m3u8"
STREAM_URL = "https://dogusdyg-eurostar.lg.mncdn.com/dogusdyg_eurostar/live.m3u8"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Referer": "https://www.startv.com.tr/",
    "Origin": "https://www.startv.com.tr",
    "Connection": "keep-alive",
}


def normalize_playlist(content: str, playlist_url: str) -> str:
    lines = []
    base = playlist_url.rsplit("/", 1)[0] + "/"

    for line in content.splitlines():
        stripped = line.strip()

        if stripped and not stripped.startswith("#") and ".m3u8" in stripped:
            line = urljoin(base, stripped)

        lines.append(line)

    return "\n".join(lines) + "\n"


def fetch_playlist(session: requests.Session) -> str:
    r = session.get(STREAM_URL, timeout=(5, 15))
    print(f"HTTP Status: {r.status_code}")

    if r.status_code != 200:
        print("Response Preview:")
        print(r.text[:500])

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
    print("=== EuroStar Direct Extractor ===")
    start = time.time()

    try:
        session = requests.Session()
        session.headers.update(HEADERS)

        playlist = fetch_playlist(session)
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
