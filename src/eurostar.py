import os
import re
import time
import requests
from urllib.parse import urljoin

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


def fetch_master(session: requests.Session, url: str) -> str:
    r = session.get(url, timeout=15)
    r.raise_for_status()

    if "#EXTM3U" not in r.text:
        raise ValueError("Keine gültige Master-M3U8 erhalten")

    return r.text, r.url


def normalize_master(content: str, master_url: str) -> str:
    lines = []
    base = master_url.rsplit("/", 1)[0] + "/"

    for line in content.splitlines():
        stripped = line.strip()

        if stripped and not stripped.startswith("#"):
            line = urljoin(base, stripped)

        lines.append(line)

    return "\n".join(lines) + "\n"


def save_playlist(content: str) -> None:
    os.makedirs("output", exist_ok=True)
    tmp = OUTPUT + ".tmp"

    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)

    os.replace(tmp, OUTPUT)


def main() -> int:
    print("=== EuroStar Extractor ===")
    start = time.time()

    try:
        session = requests.Session()
        session.headers.update(HEADERS)

        page = session.get(PAGE_URL, timeout=15)
        page.raise_for_status()

        live_url = extract_live_url(page.text)
        print(f"Live URL gefunden: {live_url}")

        master_content, master_url = fetch_master(session, live_url)
        normalized = normalize_master(master_content, master_url)

        save_playlist(normalized)

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
