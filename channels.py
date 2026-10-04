import os
import re
import time
import html
from urllib.parse import urlparse, parse_qs, unquote

import requests
from playwright.sync_api import sync_playwright


# ============================================================
# KONFIGURATION
# ============================================================

PLAYLIST_FILE = os.path.join("2026", "playlist.m3u")
STREAMS_DIR = "streams"


CHANNELS = {
    "nowtv": {
        "name": "NOW TV",
        "url": "https://www.nowtv.com.tr/canli-yayin",
        "referer": "https://www.nowtv.com.tr/",
        "logo": "https://i.ibb.co/WDfRpwV/now.jpg",
        "tvg_id": "FOX.tr",
        "cdn": [
            "ciner-live.ercdn.net/nowtv/",
            "nowtv-live-ad.ercdn.net/nowtv/",
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
#
# Nur NOW TV hat hier einen festen Fallback.
#
# SHOW TÜRK verwendet absichtlich KEINEN festen Fallback,
# weil die URL einen zeitlich begrenzten e= Token enthält.
#
# ============================================================

FALLBACK_STREAMS = {
    "nowtv": [
        "https://ciner-live.ercdn.net/nowtv/playlist.m3u8",
    ],

    "showturk": [],
}


# ============================================================
# USER AGENT
# ============================================================

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


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

    url = url.replace("\\/", "/")
    url = url.replace("\\u0026", "&")
    url = url.replace("\\u003d", "=")
    url = url.replace("\\u003F", "?")
    url = url.replace("\\u003f", "?")

    url = url.strip()
    url = url.strip('"')
    url = url.strip("'")

    # URL-Encoding zurückwandeln
    if "%3A" in url.upper():
        try:
            url = unquote(url)
        except Exception:
            pass

    return url


# ============================================================
# M3U8 AUS TEXT FINDEN
# ============================================================

def extract_m3u8_urls(text):

    if not text:
        return []

    text = html.unescape(text)

    patterns = [

        # normale URL
        r'https?://[^"\'>\s\\]+\.m3u8(?:\?[^"\'>\s\\]*)?',

        # URL encoded
        r'https?%3A%2F%2F[^"\'>\s\\]+%2Em3u8[^"\'>\s\\]*',
    ]

    found = []

    for pattern in patterns:

        matches = re.findall(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        for match in matches:

            url = normalize_url(match)

            if (
                url
                and
                ".m3u8" in url.lower()
                and
                url not in found
            ):

                found.append(url)

    return found


# ============================================================
# M3U8 URL GÜLTIG?
# ============================================================

def is_valid_m3u8_url(url):

    if not url:
        return False

    url = normalize_url(url)

    if not url.startswith(
        "http"
    ):
        return False

    if ".m3u8" not in url.lower():
        return False

    # Token-Ablauf prüfen
    try:

        parsed = urlparse(url)

        params = parse_qs(
            parsed.query
        )

        if "e" in params:

            expiry = int(
                params["e"][0]
            )

            if expiry <= int(
                time.time()
            ):

                return False

    except Exception:
        pass

    return True


# ============================================================
# CHANNEL-CDN PRÜFEN
# ============================================================

def belongs_to_channel(
    url,
    channel_key,
):

    lower = url.lower()

    channel = CHANNELS[
        channel_key
    ]

    for cdn in channel["cdn"]:

        if cdn.lower() in lower:
            return True

    return False


# ============================================================
# STREAM SCORE
# ============================================================

def stream_score(
    url,
    channel_key,
):

    lower = url.lower()

    score = 0

    # --------------------------------------------------------
    # Kanal-CDN
    # --------------------------------------------------------

    if belongs_to_channel(
        url,
        channel_key,
    ):

        score += 100

    # --------------------------------------------------------
    # Qualität
    # --------------------------------------------------------

    if "1080" in lower:
        score += 50

    elif "720" in lower:
        score += 40

    elif "576" in lower:
        score += 30

    elif "480" in lower:
        score += 20

    elif "360" in lower:
        score += 10

    # --------------------------------------------------------
    # bevorzugte Stream-Dateien
    # --------------------------------------------------------

    if "master" in lower:
        score += 25

    if "playlist.m3u8" in lower:
        score += 20

    if "index.m3u8" in lower:
        score += 15

    # --------------------------------------------------------
    # SHOW TÜRK
    # --------------------------------------------------------

    if channel_key == "showturk":

        if "showturk_720p" in lower:
            score += 50

        if "/showturk/" in lower:
            score += 30

    # --------------------------------------------------------
    # NOW TV
    # --------------------------------------------------------

    if channel_key == "nowtv":

        if "nowtv" in lower:
            score += 20

    return score


# ============================================================
# STREAM VALIDIEREN
# ============================================================

def validate_stream(
    url,
    referer,
    timeout=8,
):

    if not is_valid_m3u8_url(url):
        return False

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": (
            "application/vnd.apple.mpegurl,"
            "application/x-mpegURL,"
            "application/octet-stream,"
            "*/*"
        ),
        "Referer": referer,
        "Origin": urlparse(
            referer
        ).scheme
        + "://"
        + urlparse(
            referer
        ).netloc,
    }

    try:

        response = requests.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True,
        )

        if response.status_code != 200:
            print(
                f"    HTTP {response.status_code}"
            )

            return False

        content = response.text[
            :200000
        ]

        if "#EXTM3U" not in content:
            return False

        return True

    except Exception as exc:

        print(
            f"    Validierungsfehler: {exc}"
        )

        return False


# ============================================================
# STREAM-KANDIDAT HINZUFÜGEN
# ============================================================

def add_candidate(
    candidates,
    url,
    channel_key,
):

    url = normalize_url(url)

    if not is_valid_m3u8_url(url):
        return

    # Nur bekannte CDN-Strukturen akzeptieren
    if not belongs_to_channel(
        url,
        channel_key,
    ):

        print(
            f"  Fremder Stream ignoriert: {url}"
        )

        return

    if url not in candidates:

        candidates.append(url)

        print(
            f"  M3U8 gefunden: {url}"
        )


# ============================================================
# BROWSER SCANNER
# ============================================================

def scan_channel(
    playwright,
    channel_key,
):

    channel = CHANNELS[
        channel_key
    ]

    candidates = []

    browser = playwright.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
        ],
    )

    context = browser.new_context(
        user_agent=USER_AGENT,
        viewport={
            "width": 1920,
            "height": 1080,
        },
        locale="tr-TR",
        ignore_https_errors=True,
    )

    page = context.new_page()

    # --------------------------------------------------------
    # REQUEST / RESPONSE ABFANGEN
    # --------------------------------------------------------

    def response_handler(response):

        try:

            url = normalize_url(
                response.url
            )

            if ".m3u8" not in url.lower():
                return

            add_candidate(
                candidates,
                url,
                channel_key,
            )

        except Exception:
            pass

    page.on(
        "response",
        response_handler,
    )

    # --------------------------------------------------------
    # REQUEST ABFANGEN
    # --------------------------------------------------------

    def request_handler(request):

        try:

            url = normalize_url(
                request.url
            )

            if ".m3u8" not in url.lower():
                return

            add_candidate(
                candidates,
                url,
                channel_key,
            )

        except Exception:
            pass

    page.on(
        "request",
        request_handler,
    )

    # --------------------------------------------------------
    # RESSOURCEN
    # --------------------------------------------------------

    def route_handler(route):

        resource_type = (
            route.request.resource_type
        )

        if resource_type in {
            "image",
            "font",
            "stylesheet",
        }:

            route.abort()

        else:

            route.continue_()

    page.route(
        "**/*",
        route_handler,
    )

    try:

        print(
            f"  Lade Seite: {channel['url']}"
        )

        page.goto(
            channel["url"],
            wait_until="domcontentloaded",
            timeout=30000,
        )

        # ----------------------------------------------------
        # Erste Wartezeit
        # ----------------------------------------------------

        page.wait_for_timeout(
            4000
        )

        # ----------------------------------------------------
        # Player anklicken
        # ----------------------------------------------------

        selectors = [
            "video",
            "iframe",
            "[class*='player']",
            "[id*='player']",
            "[class*='video']",
            "[id*='video']",
            "button",
        ]

        for selector in selectors:

            try:

                locator = page.locator(
                    selector
                ).first

                if locator.is_visible(
                    timeout=1000
                ):

                    locator.click(
                        timeout=2000
                    )

                    page.wait_for_timeout(
                        1000
                    )

            except Exception:
                pass

        # ----------------------------------------------------
        # Noch 20 Sekunden beobachten
        # ----------------------------------------------------

        print(
            "  Beobachte Netzwerkverkehr..."
        )

        start = time.monotonic()

        while (
            time.monotonic() - start
            < 20
        ):

            page.wait_for_timeout(
                500
            )

        # ----------------------------------------------------
        # PERFORMANCE RESOURCES
        # ----------------------------------------------------

        try:

            resources = page.evaluate(
                """
                () => performance
                    .getEntriesByType('resource')
                    .map(x => x.name)
                """
            )

            for resource in resources:

                for url in extract_m3u8_urls(
                    resource
                ):

                    add_candidate(
                        candidates,
                        url,
                        channel_key,
                    )

        except Exception:
            pass

        # ----------------------------------------------------
        # HTML
        # ----------------------------------------------------

        try:

            source = page.content()

            for url in extract_m3u8_urls(
                source
            ):

                add_candidate(
                    candidates,
                    url,
                    channel_key,
                )

            for url in extract_m3u8_urls(
                unquote(source)
            ):

                add_candidate(
                    candidates,
                    url,
                    channel_key,
                )

        except Exception:
            pass

        # ----------------------------------------------------
        # SCRIPTS
        # ----------------------------------------------------

        try:

            scripts = page.locator(
                "script"
            ).all()

            for script in scripts:

                try:

                    text = (
                        script.text_content()
                    )

                    for url in extract_m3u8_urls(
                        text
                    ):

                        add_candidate(
                            candidates,
                            url,
                            channel_key,
                        )

                except Exception:
                    pass

        except Exception:
            pass

    except Exception as exc:

        print(
            f"  Browser-Fehler: {exc}"
        )

    finally:

        try:
            context.close()
        except Exception:
            pass

        try:
            browser.close()
        except Exception:
            pass

    # ========================================================
    # SORTIEREN
    # ========================================================

    candidates.sort(
        key=lambda url:
            stream_score(
                url,
                channel_key,
            ),
        reverse=True,
    )

    # ========================================================
    # VALIDIEREN
    # ========================================================

    print()
    print(
        f"  Kandidaten: {len(candidates)}"
    )

    for candidate in candidates:

        print(
            f"  Prüfe: {candidate}"
        )

        if validate_stream(
            candidate,
            channel["referer"],
        ):

            print(
                f"  VALID: {candidate}"
            )

            return candidate

        print(
            "  Ungültig."
        )

    return None


# ============================================================
# FALLBACK
# ============================================================

def fallback_find(
    channel_key,
):

    channel = CHANNELS[
        channel_key
    ]

    candidates = FALLBACK_STREAMS.get(
        channel_key,
        [],
    )

    for url in candidates:

        print(
            f"  Fallback prüfen: {url}"
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

def write_channel_stream(
    channel_key,
    stream,
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

        file.write(content)


# ============================================================
# LINKS.TXT
# ============================================================

def write_links(
    streams,
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

        if streams.get(
            channel_key
        ):

            lines.append(
                streams[channel_key]
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
# PLAYLIST EINTRAG FINDEN
# ============================================================

def playlist_matches(
    line,
    channel_key,
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
            "showturk" in text
        )

    return False


# ============================================================
# PLAYLIST URL AKTUALISIEREN
# ============================================================

def update_playlist(
    channel_key,
    stream,
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

    found = False

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

        found = True

        print(
            f"  Playlist-Eintrag gefunden:"
        )

        print(
            f"  {line.strip()}"
        )

        # Nächste echte URL suchen
        for next_index in range(
            index + 1,
            len(lines),
        ):

            candidate = (
                lines[next_index]
                .strip()
            )

            if not candidate:
                continue

            if candidate.startswith(
                "#"
            ):
                continue

            lines[next_index] = (
                stream + "\n"
            )

            print(
                f"  {CHANNELS[channel_key]['name']} "
                f"URL aktualisiert."
            )

            break

        break

    if not found:

        print(
            f"  Kein "
            f"{CHANNELS[channel_key]['name']}"
            f"-Eintrag gefunden."
        )

        return

    with open(
        PLAYLIST_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        file.writelines(
            lines
        )


# ============================================================
# FEHLERDATEI
# ============================================================

def write_error(
    channel_key,
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
    channel_key,
):

    path = os.path.join(
        STREAMS_DIR,
        f"{channel_key}_error.txt",
    )

    if os.path.exists(path):
        os.remove(path)


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

    with sync_playwright() as playwright:

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

            stream = scan_channel(
                playwright,
                channel_key,
            )

            # ------------------------------------------------
            # FALLBACK
            # ------------------------------------------------

            if not stream:

                print(
                    "  Kein Stream über Webseite gefunden."
                )

                stream = fallback_find(
                    channel_key
                )

            # ------------------------------------------------
            # ERFOLG
            # ------------------------------------------------

            if stream:

                streams[
                    channel_key
                ] = stream

                print()
                print(
                    f"  OK: {stream}"
                )

                write_channel_stream(
                    channel_key,
                    stream,
                )

                update_playlist(
                    channel_key,
                    stream,
                )

                remove_error(
                    channel_key
                )

            else:

                streams[
                    channel_key
                ] = None

                print()
                print(
                    f"  FEHLER: "
                    f"{channel['name']} "
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
        for value in streams.values()
        if value
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
        f"Erfolgreich: "
        f"{successful}/{len(CHANNELS)}"
    )

    print(
        f"Fehler:      "
        f"{failed}/{len(CHANNELS)}"
    )

    print()

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
