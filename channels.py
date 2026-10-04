import os
import re
import time
import html
from urllib.parse import urlparse, parse_qs, unquote

import requests


# ============================================================
# KONFIGURATION
# ============================================================

PLAYLIST_FILE = os.path.join(
    "2026",
    "playlist.m3u",
)

STREAMS_DIR = "streams"


CHANNELS = {

    "nowtv": {
        "name": "NOW TV",
        "url": "https://www.nowtv.com.tr/canli-yayin",
        "referer": "https://www.nowtv.com.tr/",
        "logo": "https://i.ibb.co/WDfRpwV/now.jpg",
        "tvg_id": "FOX.tr",

        "cdn": [
            "nowtv-live-ad.ercdn.net/nowtv/",
            "ciner-live.ercdn.net/nowtv/",
        ],
    },

    "showturk": {
        "name": "SHOW TÜRK",
        "url": "https://www.showturk.com.tr/canli-yayin",
        "referer": "https://www.showturk.com.tr/",
        "logo": "https://i.ibb.co/WvhGGP0/showturk1.png",
        "tvg_id": "",

        "cdn": [
            "ciner-live.ercdn.net/showturk/",
        ],
    },
}


# ============================================================
# FALLBACK
# ============================================================

FALLBACK_STREAMS = {

    "nowtv": [
        "https://ciner-live.ercdn.net/nowtv/playlist.m3u8",
    ],

    # Kein statischer SHOW-TÜRK-Fallback.
    #
    # Der Stream enthält:
    #
    # e=
    # st=
    # tv=
    #
    # und läuft ab.
    #
    "showturk": [],
}


# ============================================================
# HTTP
# ============================================================

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


SESSION = requests.Session()

SESSION.headers.update({
    "User-Agent": USER_AGENT,
    "Accept": (
        "text/html,"
        "application/xhtml+xml,"
        "application/xml;q=0.9,"
        "image/avif,"
        "image/webp,"
        "*/*;q=0.8"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
})


# ============================================================
# VERZEICHNISSE
# ============================================================

def ensure_directories():

    os.makedirs(
        STREAMS_DIR,
        exist_ok=True,
    )

    playlist_dir = os.path.dirname(
        PLAYLIST_FILE
    )

    if playlist_dir:

        os.makedirs(
            playlist_dir,
            exist_ok=True,
        )


# ============================================================
# URL NORMALISIEREN
# ============================================================

def normalize_url(url):

    if not url:
        return ""

    url = html.unescape(url)

    # HTML / JavaScript escaped
    url = url.replace(
        "\\/",
        "/",
    )

    url = url.replace(
        "\\u0026",
        "&",
    )

    url = url.replace(
        "\\u003d",
        "=",
    )

    url = url.replace(
        "\\u003F",
        "?",
    )

    url = url.replace(
        "\\u003f",
        "?",
    )

    url = url.strip()

    url = url.strip(
        '"'
    )

    url = url.strip(
        "'"
    )

    # URL encoded
    try:

        if "%3A" in url.upper():

            url = unquote(
                url
            )

    except Exception:
        pass

    return url


# ============================================================
# M3U8 URL GÜLTIG?
# ============================================================

def is_m3u8(url):

    if not url:
        return False

    url = normalize_url(
        url
    )

    if not url.startswith(
        "http"
    ):
        return False

    return (
        ".m3u8" in url.lower()
    )


# ============================================================
# TOKEN ABGELAUFEN?
# ============================================================

def token_expired(url):

    try:

        parsed = urlparse(
            url
        )

        params = parse_qs(
            parsed.query
        )

        if "e" not in params:
            return False

        expiry = int(
            params["e"][0]
        )

        return (
            expiry <= int(
                time.time()
            )
        )

    except Exception:

        return False


# ============================================================
# CHANNEL CDN PRÜFEN
# ============================================================

def belongs_to_channel(
    url,
    channel_key,
):

    url = normalize_url(
        url
    ).lower()

    channel = CHANNELS[
        channel_key
    ]

    for cdn in channel["cdn"]:

        if cdn.lower() in url:

            return True

    return False


# ============================================================
# STREAM VALIDIEREN
# ============================================================

def validate_stream(
    url,
    referer,
    timeout=10,
):

    url = normalize_url(
        url
    )

    if not is_m3u8(
        url
    ):

        return False

    if token_expired(
        url
    ):

        print(
            "    Token abgelaufen."
        )

        return False

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": (
            "application/vnd.apple.mpegurl,"
            "application/x-mpegURL,"
            "*/*"
        ),
        "Referer": referer,
        "Origin": (
            urlparse(
                referer
            ).scheme
            + "://"
            + urlparse(
                referer
            ).netloc
        ),
    }

    try:

        response = requests.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True,
        )

        print(
            f"    HTTP: {response.status_code}"
        )

        if response.status_code != 200:

            return False

        content = response.text[
            :200000
        ]

        if "#EXTM3U" not in content:

            return False

        return True

    except Exception as exc:

        print(
            f"    Fehler: {exc}"
        )

        return False


# ============================================================
# SHOW TÜRK DIREKT AUS data-hope-video
# ============================================================

def extract_showturk_stream(
    source
):

    if not source:
        return []

    source = html.unescape(
        source
    )

    # --------------------------------------------------------
    # 1. data-hope-video / JSON
    # --------------------------------------------------------

    pattern = (
        r'"m3u8"\s*:\s*'
        r'\[\s*\{'
        r'.*?'
        r'"src"\s*:\s*"'
        r'(.*?)"'
    )

    matches = re.findall(
        pattern,
        source,
        flags=(
            re.IGNORECASE
            |
            re.DOTALL
        ),
    )

    streams = []

    for match in matches:

        url = normalize_url(
            match
        )

        if (
            is_m3u8(url)
            and
            "ciner-live.ercdn.net/showturk/"
            in url.lower()
        ):

            if url not in streams:

                streams.append(
                    url
                )

    # --------------------------------------------------------
    # 2. Fallback: jede SHOW-TÜRK-M3U8 im HTML
    # --------------------------------------------------------

    if not streams:

        pattern = (
            r'https?:\\/\\/'
            r'ciner-live\.ercdn\.net'
            r'\\/showturk'
            r'\\/[^"\']+?\.m3u8'
            r'(?:\?[^"\']*)?'
        )

        matches = re.findall(
            pattern,
            source,
            flags=re.IGNORECASE,
        )

        for match in matches:

            url = normalize_url(
                match
            )

            if url not in streams:

                streams.append(
                    url
                )

    return streams


# ============================================================
# ALLGEMEINE M3U8-SUCHE
# ============================================================

def extract_m3u8_urls(
    source
):

    if not source:
        return []

    source = html.unescape(
        source
    )

    # Escaped slashes zuerst
    source = source.replace(
        "\\/",
        "/"
    )

    pattern = (
        r'https?://'
        r'[^"\'>\s]+?'
        r'\.m3u8'
        r'(?:\?[^"\'>\s]*)?'
    )

    matches = re.findall(
        pattern,
        source,
        flags=re.IGNORECASE,
    )

    streams = []

    for match in matches:

        url = normalize_url(
            match
        )

        if (
            is_m3u8(url)
            and
            url not in streams
        ):

            streams.append(
                url
            )

    return streams


# ============================================================
# STREAM AUS SEITE FINDEN
# ============================================================

def find_stream(
    channel_key
):

    channel = CHANNELS[
        channel_key
    ]

    print(
        f"  Lade Seite: {channel['url']}"
    )

    try:

        response = SESSION.get(
            channel["url"],
            headers={
                "Referer": channel["referer"],
            },
            timeout=30,
        )

        print(
            f"  Seitenstatus: "
            f"{response.status_code}"
        )

        if response.status_code != 200:

            return None

        source = response.text

    except Exception as exc:

        print(
            f"  Seitenfehler: {exc}"
        )

        return None

    candidates = []

    # ========================================================
    # SHOW TÜRK
    # ========================================================

    if channel_key == "showturk":

        print(
            "  Suche SHOW TÜRK data-hope-video..."
        )

        candidates.extend(
            extract_showturk_stream(
                source
            )
        )

    # ========================================================
    # ALLGEMEINE M3U8-SUCHE
    # ========================================================

    candidates.extend(
        extract_m3u8_urls(
            source
        )
    )

    # ========================================================
    # FILTERN
    # ========================================================

    unique = []

    for url in candidates:

        url = normalize_url(
            url
        )

        if not is_m3u8(
            url
        ):

            continue

        if not belongs_to_channel(
            url,
            channel_key,
        ):

            continue

        if token_expired(
            url
        ):

            print(
                f"  Token abgelaufen: {url}"
            )

            continue

        if url not in unique:

            unique.append(
                url
            )

    # ========================================================
    # SCORE
    # ========================================================

    def score(url):

        lower = url.lower()

        value = 0

        if "playlist.m3u8" in lower:

            value += 100

        if "720p" in lower:

            value += 80

        if "1080p" in lower:

            value += 90

        if "master" in lower:

            value += 70

        if channel_key == "showturk":

            if "/showturk/" in lower:

                value += 100

        return value

    unique.sort(
        key=score,
        reverse=True,
    )

    # ========================================================
    # PRÜFEN
    # ========================================================

    print(
        f"  Kandidaten gefunden: "
        f"{len(unique)}"
    )

    for url in unique:

        print(
            f"  Prüfe: {url}"
        )

        if validate_stream(
            url,
            channel["referer"],
        ):

            print(
                f"  ✓ Stream gültig"
            )

            return url

        print(
            f"  ✗ Stream ungültig"
        )

    return None


# ============================================================
# FALLBACK
# ============================================================

def fallback_stream(
    channel_key
):

    channel = CHANNELS[
        channel_key
    ]

    candidates = FALLBACK_STREAMS.get(
        channel_key,
        []
    )

    for url in candidates:

        print(
            f"  Fallback: {url}"
        )

        if validate_stream(
            url,
            channel["referer"],
        ):

            return url

    return None


# ============================================================
# STREAM-DATEI SCHREIBEN
# ============================================================

def write_stream_file(
    channel_key,
    stream
):

    channel = CHANNELS[
        channel_key
    ]

    path = os.path.join(
        STREAMS_DIR,
        f"{channel_key}.m3u",
    )

    if channel["tvg_id"]:

        extinf = (
            f'#EXTINF:-1 '
            f'tvg-id="{channel["tvg_id"]}" '
            f'tvg-logo="{channel["logo"]}",'
            f'{channel["name"]}'
        )

    else:

        extinf = (
            f'#EXTINF:-1 '
            f'tvg-logo="{channel["logo"]}",'
            f'{channel["name"]}'
        )

    content = (
        "#EXTM3U\n"
        + extinf
        + "\n"
        + stream
        + "\n"
    )

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as file:

        file.write(
            content
        )


# ============================================================
# PLAYLIST EINTRAG ERKENNEN
# ============================================================

def playlist_matches(
    line,
    channel_key
):

    text = line.lower()

    if channel_key == "nowtv":

        return (
            "now tv" in text
            or
            "nowtv" in text
        )

    if channel_key == "showturk":

        return (
            "show türk" in text
            or
            "showtürk" in text
            or
            "showturk" in text
        )

    return False


# ============================================================
# PLAYLIST AKTUALISIEREN
# ============================================================

def update_playlist(
    channel_key,
    stream
):

    if not os.path.exists(
        PLAYLIST_FILE
    ):

        print(
            f"  Playlist nicht gefunden: "
            f"{PLAYLIST_FILE}"
        )

        return

    with open(
        PLAYLIST_FILE,
        "r",
        encoding="utf-8",
    ) as file:

        lines = file.readlines()

    channel = CHANNELS[
        channel_key
    ]

    for index, line in enumerate(
        lines
    ):

        if not line.startswith(
            "#EXTINF"
        ):

            continue

        if not playlist_matches(
            line,
            channel_key,
        ):

            continue

        print(
            f"  {channel['name']}-Eintrag gefunden."
        )

        # ----------------------------------------------------
        # Nächste URL
        # ----------------------------------------------------

        for next_index in range(
            index + 1,
            len(lines),
        ):

            value = (
                lines[next_index]
                .strip()
            )

            if not value:

                continue

            if value.startswith(
                "#"
            ):

                continue

            lines[next_index] = (
                stream + "\n"
            )

            print(
                f"  URL aktualisiert:"
            )

            print(
                f"  {stream}"
            )

            with open(
                PLAYLIST_FILE,
                "w",
                encoding="utf-8",
            ) as file:

                file.writelines(
                    lines
                )

            return True

    print(
        f"  Kein {channel['name']}-Eintrag "
        f"in der Playlist gefunden."
    )

    return False


# ============================================================
# FEHLERDATEI
# ============================================================

def write_error(
    channel_key
):

    channel = CHANNELS[
        channel_key
    ]

    path = os.path.join(
        STREAMS_DIR,
        f"{channel_key}_error.txt",
    )

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as file:

        file.write(
            f"Kanal: {channel['name']}\n"
        )

        file.write(
            f"URL: {channel['url']}\n"
        )

        file.write(
            "Status: M3U8 nicht gefunden\n"
        )


def remove_error(
    channel_key
):

    path = os.path.join(
        STREAMS_DIR,
        f"{channel_key}_error.txt",
    )

    if os.path.exists(
        path
    ):

        os.remove(
            path
        )


# ============================================================
# LINKS.TXT
# ============================================================

def write_links(
    streams
):

    path = os.path.join(
        STREAMS_DIR,
        "links.txt",
    )

    lines = []

    for channel_key in CHANNELS:

        channel = CHANNELS[
            channel_key
        ]

        lines.append(
            f"### {channel['name']}"
        )

        stream = streams.get(
            channel_key
        )

        if stream:

            lines.append(
                stream
            )

        else:

            lines.append(
                "NICHT GEFUNDEN"
            )

        lines.append("")

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as file:

        file.write(
            "\n".join(lines)
        )


# ============================================================
# HAUPTPROGRAMM
# ============================================================

def main():

    ensure_directories()

    print("=" * 70)
    print("IPTV SENDER-SCANNER")
    print("=" * 70)

    print(
        f"Playlist: {PLAYLIST_FILE}"
    )

    print(
        f"Sender: {len(CHANNELS)}"
    )

    print("=" * 70)

    streams = {}

    for channel_key in CHANNELS:

        channel = CHANNELS[
            channel_key
        ]

        print()
        print("-" * 70)

        print(
            f"Kanal: {channel['name']}"
        )

        print(
            f"URL: {channel['url']}"
        )

        print("-" * 70)

        stream = find_stream(
            channel_key
        )

        # ----------------------------------------------------
        # FALLBACK
        # ----------------------------------------------------

        if not stream:

            print(
                "  Kein Stream über Webseite gefunden."
            )

            stream = fallback_stream(
                channel_key
            )

        # ----------------------------------------------------
        # ERFOLG
        # ----------------------------------------------------

        if stream:

            streams[
                channel_key
            ] = stream

            print()
            print(
                f"  ✓ {channel['name']}"
            )

            print(
                f"  -> {stream}"
            )

            write_stream_file(
                channel_key,
                stream
            )

            update_playlist(
                channel_key,
                stream
            )

            remove_error(
                channel_key
            )

        # ----------------------------------------------------
        # FEHLER
        # ----------------------------------------------------

        else:

            streams[
                channel_key
            ] = None

            print()
            print(
                f"  ✗ {channel['name']} "
                f"M3U8 nicht gefunden"
            )

            write_error(
                channel_key
            )

    # --------------------------------------------------------
    # LINKS
    # --------------------------------------------------------

    write_links(
        streams
    )

    # ========================================================
    # ABSCHLUSS
    # ========================================================

    successful = sum(
        1
        for stream in streams.values()
        if stream
    )

    failed = (
        len(CHANNELS)
        - successful
    )

    print()
    print("=" * 70)
    print("SCAN ABGESCHLOSSEN")
    print("=" * 70)

    print(
        f"Erfolgreich: {successful}/{len(CHANNELS)}"
    )

    print(
        f"Fehler:      {failed}/{len(CHANNELS)}"
    )

    for channel_key in CHANNELS:

        channel = CHANNELS[
            channel_key
        ]

        if streams.get(
            channel_key
        ):

            print(
                f"  ✓ {channel['name']}"
            )

        else:

            print(
                f"  ✗ {channel['name']}"
            )

    print()
    print(
        f"Playlist: {PLAYLIST_FILE}"
    )

    print(
        f"Streams:  {STREAMS_DIR}/"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()
