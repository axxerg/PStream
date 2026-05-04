import os
import re
import time
import requests

OUTPUT = "output/eurostar.m3u8"
PAGE_URL = "https://www.eurostartv.com.tr/canli-izle"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.eurostartv.com.tr/",
    "Origin": "https://www.eurostartv.com.tr",
    "Connection": "keep-alive",
}


def extract_live_url(html: str) -> str:
    match = re.search(r"var\s+liveUrl\s*=\s*'([^']+)'", html)
    if not match:
        raise ValueError("liveUrl nicht gefunden")
    return match.group(1)


def save_playlist(url: str) -> None:
    os.makedirs("output", exist_ok=True)
    tmp = OUTPUT + ".tmp"

    content = (
        "#EXTM3U\n"
        "#EXT-X-VERSION:3\n"
        "#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=1500000,RESOLUTION=1920x1080\n"
        f"{url}\n"
    )

    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)

    os.replace(tmp, OUTPUT)


def main() -> int:
    print("=== EuroStar Extractor ===")
    start = time.time()

    try:
        r = requests.get(PAGE_URL, headers=HEADERS, timeout=15)
        r.raise_for_status()

        live_url = extract_live_url(r.text)
        print(f"Live URL gefunden: {live_url}")

        save_playlist(live_url)

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
