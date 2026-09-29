import json
import os
import re
import time
from urllib.parse import parse_qs, urlencode, urlparse

import requests


PAGE_URL = "https://www.atv.com.tr/canli-yayin"
OUTPUT = "output/atv.m3u8"

WEBSITE_ID = "0FE2A405-8AFA-4238-B429-E5F96AEC3A5C"

BASE_STREAM_URL = (
    "https://trkvz.daioncdn.net/atv/atv.m3u8"
)

SECURE_TOKEN_URL = (
    "https://securevideotoken.tmgrup.com.tr/webtv/secure"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": (
        "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"
    ),
    "Referer": PAGE_URL,
    "Origin": "https://www.atv.com.tr",
}


def get_session():
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def get_page(session):
    print("🌐 Lade ATV Live-Seite ...")

    response = session.get(
        PAGE_URL,
        timeout=(10, 30),
    )

    response.raise_for_status()

    print("✅ ATV-Seite geladen")

    return response.text


def find_player_config(html):
    """
    Sucht den TMD-Live-Player im ATV-HTML.
    """

    print("🔎 Suche ATV Player-Konfiguration ...")

    # data-websiteid
    website_match = re.search(
        r'data-websiteid=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )

    # data-videoid
    video_match = re.search(
        r'data-videoid=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )

    # data-sid
    sid_match = re.search(
        r'data-sid=["\']([^"\']+)["\']',
        html,
        re.IGNORECASE,
    )

    website_id = (
        website_match.group(1)
        if website_match
        else WEBSITE_ID
    )

    video_id = (
        video_match.group(1)
        if video_match
        else "00000000-0000-0000-0000-000000000000"
    )

    session_id = (
        sid_match.group(1)
        if sid_match
        else ""
    )

    print()
    print("📺 ATV Player:")
    print(f"   Website ID : {website_id}")
    print(f"   Video ID   : {video_id}")

    if session_id:
        print(f"   Session ID : {session_id}")

    return {
        "websiteId": website_id,
        "videoId": video_id,
        "sessionId": session_id,
    }


def get_direct_stream_url(session):
    """
    Erzeugt die von PlayerDaion verwendete ATV-Live-URL.

    Desktop:
    d1ce2d40-5256-4550-b02e-e73c185a314e

    Diese URL ist nur die Basis.
    Falls ZTK aktiviert ist, wird danach der Secure-Token
    angefordert.
    """

    return (
        BASE_STREAM_URL
        + "?ce=3"
        + "&app=d1ce2d40-5256-4550-b02e-e73c185a314e"
    )


def request_secure_url(session, stream_url):
    """
    Entspricht dem JavaScript:

        /webtv/secure?...&url=<stream_url>

    Die Antwort enthält videoUrls.Url.
    """

    print()
    print("🔐 Fordere aktuelle ATV Secure-URL an ...")

    random_number = str(
        int(time.time() * 1000) % 1000000
    )

    headers = {
        **HEADERS,
        "X-isApp": "false",
        "X-Rand": str(
            int(time.time() * 1000)
        ),
        "Accept": "application/json",
    }

    params = {
        "url": stream_url,
    }

    response = session.get(
        SECURE_TOKEN_URL + "?" + random_number,
        params=params,
        headers=headers,
        timeout=(10, 30),
    )

    response.raise_for_status()

    data = response.json()

    print("✅ Secure-Server antwortet")

    if not isinstance(data, dict):
        raise RuntimeError(
            "Secure-Token-Antwort ist kein JSON-Objekt."
        )

    # Genau wie im Player:
    # videoUrls.Url
    url = data.get("Url")

    if isinstance(url, str) and url.strip():
        print()
        print("🔗 Aktuelle ATV URL:")
        print(url)

        return url.strip()

    # Fallback für andere Schreibweise
    url = data.get("url")

    if isinstance(url, str) and url.strip():
        print()
        print("🔗 Aktuelle ATV URL:")
        print(url)

        return url.strip()

    print()
    print("❌ Keine Url in Secure-Antwort gefunden.")
    print()
    print(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        )
    )

    raise RuntimeError(
        "Secure-Server liefert keine Url."
    )


def download_playlist(session, stream_url):
    """
    Lädt die aktuelle M3U8.
    """

    print()
    print("📥 Lade aktuelle M3U8 ...")
    print(stream_url)

    headers = {
        **HEADERS,
        "Accept": (
            "application/vnd.apple.mpegurl,"
            "application/x-mpegURL,"
            "*/*"
        ),
    }

    response = session.get(
        stream_url,
        headers=headers,
        timeout=(10, 30),
    )

    response.raise_for_status()

    content = response.text

    if "#EXTM3U" not in content:
        print()
        print("❌ Server liefert keine M3U8.")
        print()
        print(content[:1000])

        raise RuntimeError(
            "Ungültige M3U8-Antwort."
        )

    print("✅ M3U8 erfolgreich geladen")

    return content


def normalize_playlist(content, stream_url):
    """
    Falls ATV eine Master-Playlist mit relativen URLs liefert,
    werden die relativen URLs gegen die aktuelle Stream-URL
    aufgelöst.

    Wichtig:
    Query-Parameter der signierten ATV-URL bleiben erhalten,
    sofern die Unter-URLs relativ sind.
    """

    from urllib.parse import urljoin

    lines = content.splitlines()

    result = []

    for line in lines:

        stripped = line.strip()

        if (
            stripped
            and not stripped.startswith("#")
            and not stripped.startswith("http://")
            and not stripped.startswith("https://")
        ):
            absolute = urljoin(
                stream_url,
                stripped,
            )

            result.append(absolute)

        else:
            result.append(line)

    return "\n".join(result) + "\n"


def save_playlist(content):
    os.makedirs(
        os.path.dirname(OUTPUT),
        exist_ok=True,
    )

    temp_file = OUTPUT + ".tmp"

    with open(
        temp_file,
        "w",
        encoding="utf-8",
        newline="\n",
    ) as file:

        file.write(content)

    os.replace(
        temp_file,
        OUTPUT,
    )

    print()
    print(f"💾 Gespeichert: {OUTPUT}")


def main():

    print()
    print("==============================================")
    print("              ATV LIVE EXTRACTOR")
    print("==============================================")
    print()

    start = time.time()

    session = get_session()

    try:

        # ------------------------------------------------
        # 1. ATV-Seite laden
        # ------------------------------------------------

        html = get_page(session)

        player_config = find_player_config(
            html
        )

        # ------------------------------------------------
        # 2. Aktuelle DAION Basis-URL erzeugen
        # ------------------------------------------------

        direct_url = get_direct_stream_url(
            session
        )

        print()
        print("🎯 DAION Basis:")
        print(direct_url)

        # ------------------------------------------------
        # 3. Zuerst Secure-URL anfordern
        # ------------------------------------------------

        try:

            stream_url = request_secure_url(
                session,
                direct_url,
            )

        except Exception as secure_error:

            print()
            print(
                "⚠️ Secure-Token konnte nicht "
                "angefordert werden:"
            )
            print(secure_error)

            print()
            print(
                "➡️ Versuche direkte DAION-URL ..."
            )

            stream_url = direct_url

        # ------------------------------------------------
        # 4. Aktuelle M3U8 laden
        # ------------------------------------------------

        playlist = download_playlist(
            session,
            stream_url,
        )

        # ------------------------------------------------
        # 5. Relative URLs korrekt auflösen
        # ------------------------------------------------

        playlist = normalize_playlist(
            playlist,
            stream_url,
        )

        # ------------------------------------------------
        # 6. output/atv.m3u8 schreiben
        # ------------------------------------------------

        save_playlist(
            playlist
        )

        # ------------------------------------------------
        # Fertig
        # ------------------------------------------------

        duration = round(
            time.time() - start,
            2,
        )

        print()
        print("==============================================")
        print("                    FERTIG")
        print("==============================================")
        print()
        print(f"⏱️ Dauer: {duration} Sekunden")
        print(f"📁 Datei: {OUTPUT}")
        print()

        return 0

    except requests.HTTPError as error:

        print()
        print("❌ HTTP-Fehler:")
        print(error)
        print()

        return 1

    except requests.RequestException as error:

        print()
        print("❌ Netzwerkfehler:")
        print(error)
        print()

        return 2

    except Exception as error:

        print()
        print(
            f"❌ {type(error).__name__}: {error}"
        )
        print()

        return 3


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
