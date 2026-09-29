import re
import html
import requests
from pathlib import Path
from urllib.parse import unquote


PAGE_URL = "https://www.atv.com.tr/canli-yayin"
OUTPUT_FILE = Path("output/atv.m3u8")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}


def find_atv_avrupa_url(text):
    """
    Sucht nach einer bereits signierten ATV-Avrupa-M3U8-URL.

    Gesucht wird ausschließlich:
        trkvz-live.ercdn.net/atvavrupa/...
    """

    text = html.unescape(text)

    # Mehrfach URL-dekodieren, falls die URL escaped/encoded eingebettet ist
    for _ in range(3):
        decoded = unquote(text)
        if decoded == text:
            break
        text = decoded

    patterns = [
        # vollständige signierte URL
        r'https://trkvz-live\.ercdn\.net/atvavrupa/'
        r'atvavrupa_[^"\'\s<>\\]+\.m3u8'
        r'\?[^"\'\s<>\\]+',

        # allgemeiner ATV-Avrupa Stream
        r'https://trkvz-live\.ercdn\.net/atvavrupa/'
        r'[^"\'\s<>\\]+\.m3u8'
        r'\?[^"\'\s<>\\]+',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            url = match.group(0)

            # JSON/HTML-Escapes entfernen
            url = url.replace("\\/", "/")
            url = url.replace("\\u0026", "&")
            url = url.replace("&amp;", "&")

            if "st=" in url and "e=" in url:
                return url

    return None


def get_atv_page():
    session = requests.Session()
    session.headers.update(HEADERS)

    response = session.get(
        PAGE_URL,
        timeout=30,
    )

    response.raise_for_status()

    return session, response.text


def get_stream():
    session, page = get_atv_page()

    print("ATV-Seite geladen.")
    print("Suche signierte ATV Avrupa URL...")

    # 1. Direkt im HTML suchen
    url = find_atv_avrupa_url(page)

    if url:
        print("ATV Avrupa URL gefunden:")
        print(url)
        return url

    # 2. Falls die URL in eingebettetem JavaScript escaped ist,
    #    noch einmal nach typischen Varianten suchen.
    candidates = re.findall(
        r'https?[^"\']+atvavrupa[^"\']+',
        html.unescape(page),
        re.IGNORECASE,
    )

    for candidate in candidates:
        candidate = candidate.replace("\\/", "/")
        candidate = candidate.replace("\\u0026", "&")
        candidate = candidate.replace("&amp;", "&")

        if (
            "trkvz-live.ercdn.net/atvavrupa/" in candidate
            and ".m3u8" in candidate
            and "st=" in candidate
            and "e=" in candidate
        ):
            print("ATV Avrupa URL gefunden:")
            print(candidate)
            return candidate

    # 3. Keine signierte URL gefunden
    print()
    print("FEHLER: Keine signierte ATV Avrupa URL gefunden.")
    print()
    print("Die Seite liefert offenbar die URL erst über JavaScript/TMD.")
    print("Es wird NICHT auf die nackte CDN-URL zurückgefallen,")
    print("weil diese mit HTTP 403 antwortet.")
    print()

    # Debug-Datei speichern
    debug_file = Path("output/atv_debug.html")
    debug_file.parent.mkdir(parents=True, exist_ok=True)
    debug_file.write_text(page, encoding="utf-8")

    print(f"Debug-HTML gespeichert: {debug_file}")

    raise RuntimeError(
        "Keine signierte ATV Avrupa M3U8-URL gefunden."
    )


def write_m3u(stream_url):
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    content = (
        "#EXTM3U\n"
        "#EXTINF:-1,ATV Avrupa\n"
        f"{stream_url}\n"
    )

    OUTPUT_FILE.write_text(
        content,
        encoding="utf-8",
    )

    print()
    print("======================================")
    print("ATV Avrupa M3U8 erfolgreich erstellt")
    print("======================================")
    print(f"Datei: {OUTPUT_FILE}")
    print()
    print(content)


def main():
    stream_url = get_stream()
    write_m3u(stream_url)


if __name__ == "__main__":
    main()
