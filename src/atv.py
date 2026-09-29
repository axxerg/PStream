import re
import requests
from pathlib import Path

PAGE_URL = "https://www.atv.com.tr/canli-yayin"

# ATV Avrupa
BASE_URL = "https://trkvz-live.ercdn.net/atvavrupa/atvavrupa_576p.m3u8"

OUTPUT = Path("output/atv.m3u8")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    )
}


def get_atv_avrupa_stream():
    session = requests.Session()
    session.headers.update(HEADERS)

    # ATV-Seite laden
    r = session.get(PAGE_URL, timeout=20)
    r.raise_for_status()

    html = r.text

    print("ATV-Seite geladen.")

    # Prüfen, ob die Seite den europäischen Player verwendet
    if "atvavrupa" not in html.lower():
        print("Hinweis: 'atvavrupa' wurde nicht direkt im HTML gefunden.")

    # ---------------------------------------------------------
    # Stream abrufen
    #
    # Der Stream benötigt einen aktuellen Token.
    # Deshalb wird die M3U8-Datei zunächst ohne Token angefragt.
    # ---------------------------------------------------------

    r = session.get(BASE_URL, timeout=20, allow_redirects=True)

    print("HTTP:", r.status_code)
    print("Final URL:", r.url)

    r.raise_for_status()

    # Falls der CDN-Server auf eine signierte URL weiterleitet,
    # verwenden wir diese URL.
    stream_url = r.url

    if "atvavrupa" not in stream_url.lower():
        raise RuntimeError(
            f"Es wurde nicht ATV Avrupa zurückgegeben:\n{stream_url}"
        )

    print("ATV Avrupa gefunden:")
    print(stream_url)

    return stream_url


def main():
    try:
        stream_url = get_atv_avrupa_stream()

        OUTPUT.parent.mkdir(parents=True, exist_ok=True)

        # M3U8-Datei erzeugen
        content = (
            "#EXTM3U\n"
            "#EXTINF:-1,ATV Avrupa\n"
            f"{stream_url}\n"
        )

        OUTPUT.write_text(content, encoding="utf-8")

        print()
        print("================================")
        print("ATV M3U8 erfolgreich erstellt")
        print("================================")
        print(OUTPUT)
        print(stream_url)

    except Exception as e:
        print("FEHLER:", e)
        raise


if __name__ == "__main__":
    main()
