import os
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

OUTPUT = "output/showturk.m3u8"
URL = "https://ciner-live.ercdn.net/showturk/playlist.m3u8"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.showturk.com.tr/",
    "Origin": "https://www.showturk.com.tr",
    "Accept": "*/*",
    "Connection": "keep-alive",
}

CONNECT_TIMEOUT = 5
READ_TIMEOUT = 15
MAX_RETRIES = 3
MIN_SIZE = 32  # minimale plausible M3U8-Größe in Bytes


def build_session() -> requests.Session:
    """Create a hardened HTTP session with retries."""
    retry = Retry(
        total=MAX_RETRIES,
        connect=MAX_RETRIES,
        read=MAX_RETRIES,
        status=MAX_RETRIES,
        backoff_factor=2,
        status_forcelist=(403, 429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "HEAD"]),
        raise_on_status=False,
    )

    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)

    session = requests.Session()
    session.headers.update(HEADERS)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def validate_m3u8(text: str, content_type: str) -> tuple[bool, str]:
    """Validate that the response looks like a real M3U8 playlist."""
    if not text:
        return False, "Leere Antwort"

    stripped = text.strip()

    if len(stripped) < MIN_SIZE:
        return False, "Antwort zu klein"

    if "<html" in stripped.lower():
        return False, "HTML statt M3U8 erhalten"

    if "#EXTM3U" not in stripped:
        return False, "Kein #EXTM3U Header gefunden"

    if "mpegurl" not in content_type.lower() and "application/octet-stream" not in content_type.lower():
        # nicht hart ablehnen, nur Hinweis
        print(f"⚠️ Ungewöhnlicher Content-Type: {content_type}")

    return True, "OK"


def atomic_write(path: str, content: str) -> None:
    """Write file atomically to avoid partial/corrupt writes."""
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    os.replace(tmp, path)


def fetch_playlist(session: requests.Session) -> str:
    """Fetch playlist from remote CDN."""
    response = session.get(URL, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")
    text = response.text

    print(f"🌍 Final URL: {response.url}")
    print(f"📦 HTTP {response.status_code} | Content-Type: {content_type}")

    valid, reason = validate_m3u8(text, content_type)
    if not valid:
        raise ValueError(reason)

    return text


def main() -> int:
    print("=== ShowTurk Extractor ===")
    start = time.time()
    os.makedirs("output", exist_ok=True)

    try:
        session = build_session()
        playlist = fetch_playlist(session)
        atomic_write(OUTPUT, playlist)

        duration = round(time.time() - start, 2)
        print("✅ Stream gefunden")
        print(f"💾 gespeichert: {OUTPUT}")
        print(f"⏱️ Dauer: {duration}s")
        return 0

    except requests.HTTPError as e:
        print(f"❌ HTTP Fehler: {e}")
        return 1

    except requests.RequestException as e:
        print(f"❌ Netzwerkfehler: {e}")
        return 2

    except (OSError, ValueError) as e:
        print(f"❌ Verarbeitungsfehler: {e}")
        return 3

    except Exception as e:
        print(f"❌ Unerwarteter Fehler: {type(e).__name__}: {e}")
        return 99


if __name__ == "__main__":
    raise SystemExit(main())
