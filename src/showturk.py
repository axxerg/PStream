import json
import os
import re
import time
import requests
from urllib.parse import urljoin


PAGE_URL = "https://www.showturk.com.tr/canli-yayin"
OUTPUT = "output/showturk.m3u8"

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
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.showturk.com.tr/",
}


def fetch_page(session):
    print("🌍 Lade ShowTürk-Seite ...")

    response = session.get(
        PAGE_URL,
        headers=HEADERS,
        timeout=(10, 20),
    )

    response.raise_for_status()

    print(f"✅ Webseite geladen: HTTP {response.status_code}")

    return response.text


def extract_master_url(page):
    print("🔎 Suche data-hope-video ...")

    # data-hope-video='{...}'
    match = re.search(
        r'data-hope-video=[\'"](.+?)[\'"]\s*>',
        page,
        re.DOTALL,
    )

    if not match:
        raise ValueError("data-hope-video wurde nicht gefunden")

    json_text = match.group(1)

    # HTML/JSON-Escapes zurückwandeln
    json_text = (
        json_text
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&amp;", "&")
        .replace("\\/", "/")
    )

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"data-hope-video konnte nicht als JSON gelesen werden: {e}"
        )

    try:
        url = data["media"]["m3u8"][0]["src"]
    except (KeyError, IndexError, TypeError):
        raise ValueError(
            "media.m3u8[0].src wurde im data-hope-video nicht gefunden"
        )

    if not url.startswith(("http://", "https://")):
        url = urljoin(PAGE_URL, url)

    print("✅ Aktuelle Master-M3U8 gefunden:")
    print(url)

    return url


def fetch_master_playlist(session, master_url):
    print("📡 Lade Master-M3U8 ...")

    headers = {
        "User-Agent": HEADERS["User-Agent"],
        "Accept": "*/*",
        "Referer": PAGE_URL,
        "Origin": "https://www.showturk.com.tr",
    }

    response = session.get(
        master_url,
        headers=headers,
        timeout=(10, 20),
    )

    response.raise_for_status()

    content = response.text

    if "#EXTM3U" not in content:
        raise ValueError("Die Antwort ist keine gültige M3U8-Datei")

    print("✅ Master-M3U8 erfolgreich geladen")

    return content, response.url


def normalize_playlist(content, master_url):
    """
    Macht relative URLs in der Master-Playlist absolut.
    Absolute URLs bleiben unverändert.
    """

    result = []

    base_url = master_url.rsplit("/", 1)[0] + "/"

    for line in content.splitlines():
        line = line.strip()

        if (
            line
            and not line.startswith("#")
            and not line.startswith("http://")
            and not line.startswith("https://")
        ):
            line = urljoin(base_url, line)

        result.append(line)

    return "\n".join(result) + "\n"


def save_playlist(content):
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)

    temp_file = OUTPUT + ".tmp"

    with open(temp_file, "w", encoding="utf-8", newline="\n") as file:
        file.write(content)

    os.replace(temp_file, OUTPUT)

    print(f"💾 Gespeichert: {OUTPUT}")


def main():
    print()
    print("======================================")
    print("       SHOWTÜRK M3U8 EXTRACTOR")
    print("======================================")
    print()

    start = time.time()

    try:
        session = requests.Session()

        # 1. ShowTürk-Seite laden
        page = fetch_page(session)

        # 2. aktuellen signierten M3U8-Link aus data-hope-video holen
        master_url = extract_master_url(page)

        # 3. Master-M3U8 herunterladen
        playlist, final_url = fetch_master_playlist(
            session,
            master_url,
        )

        # 4. URLs normalisieren
        playlist = normalize_playlist(
            playlist,
            final_url,
        )

        # 5. Playlist speichern
        save_playlist(playlist)

        print()
        print("======================================")
        print("              FERTIG")
        print("======================================")
        print(f"⏱️ Dauer: {round(time.time() - start, 2)} Sekunden")
        print()
        print("Die erzeugte Datei ist:")
        print(os.path.abspath(OUTPUT))
        print()

        return 0

    except requests.HTTPError as e:
        print()
        print(f"❌ HTTP-Fehler: {e}")
        return 1

    except requests.RequestException as e:
        print()
        print(f"❌ Netzwerkfehler: {e}")
        return 2

    except (ValueError, KeyError, IndexError) as e:
        print()
        print(f"❌ Fehler beim Auslesen: {e}")
        return 3

    except OSError as e:
        print()
        print(f"❌ Datei-/Systemfehler: {e}")
        return 4

    except Exception as e:
        print()
        print(f"❌ Unerwarteter Fehler: {type(e).__name__}: {e}")
        return 99


if __name__ == "__main__":
    raise SystemExit(main())
