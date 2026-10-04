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
        "logo": "https://i.ibb.co/WDfRpwV/now.jpg",
        "tvg_id": "FOX.tr",
    },

    "showturk": {
        "name": "SHOW TÜRK",
        "url": "https://www.showturk.com.tr/canli-yayin",
        "logo": "https://i.ibb.co/WvhGGP0/showturk1.png",
        "tvg_id": "",
    },
}


# ============================================================
# FALLBACK
# ============================================================

FALLBACK_STREAMS = {
    "nowtv": [
        "https://ciner-live.ercdn.net/nowtv/playlist.m3u8",
    ],

    "showturk": [],
}


# ============================================================
# REFERER
# ============================================================

REFERERS = {
    "nowtv": "https://www.nowtv.com.tr/",
    "showturk": "https://www.showturk.com.tr/",
}


# ============================================================
# HILFSFUNKTIONEN
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


def normalize_url(url):

    if not url:
        return ""

    url = html.unescape(url)

    url = url.replace("\\/", "/")
    url = url.replace("\\u0026", "&")
    url = url.replace("\\u003d", "=")
    url = url.replace("\\u003F", "?")
    url = url.replace("\\u003f", "?")

    return (
        url
        .strip()
        .strip('"')
        .strip("'")
    )


def extract_urls(text):

    if not text:
        return []

    found = []

    patterns = [
        r'https?://[^"\'>\s\\]+\.m3u8(?:\?[^"\'>\s\\]*)?',
        r'https?%3A%2F%2F[^"\'>\s\\]+%2Em3u8[^"\'>\s\\]*',
    ]

    for pattern in patterns:

        matches = re.findall(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        for match in matches:

            url = normalize_url(match)

            if "%3A" in url.upper():
                url = unquote(url)

            if ".m3u8" in url.lower():
                found.append(url)

    return found


def extract_m3u8(text):

    urls = extract_urls(text)

    unique = []

    for url in urls:

        if url not in unique:
            unique.append(url)

    return unique


def token_expired(url):

    try:

        parsed = urlparse(url)

        params = parse_qs(
            parsed.query
        )

        if "e" not in params:
            return False

        expiry = int(
            params["e"][0]
        )

        return expiry <= int(time.time())

    except Exception:
        return False


def is_valid_m3u8_url(url):

    if not url:
        return False

    url = normalize_url(url)

    if ".m3u8" not in url.lower():
        return False

    if token_expired(url):
        return False

    return True


# ============================================================
# SENDER-SPEZIFISCHE STREAM-PRÜFUNG
# ============================================================

def is_channel_stream(
    url,
    channel_key,
):

    lower = url.lower()

    # --------------------------------------------------------
    # NOW TV
    # --------------------------------------------------------

    if channel_key == "nowtv":

        return (
            "nowtv-live-ad.ercdn.net/nowtv"
            in lower
            or
            "ciner-live.ercdn.net/nowtv"
            in lower
            or
            "/nowtv/" in lower
        )

    # --------------------------------------------------------
    # SHOW TÜRK
    # --------------------------------------------------------

    if channel_key == "showturk":

        return (
            "showturk" in lower
            or
            "showturk-live" in lower
            or
            "showtv" in lower
        )

    return False


# ============================================================
# STREAM-QUALITÄT
# ============================================================

def quality_from_url(url):

    text = url.lower()

    match = re.search(
        r'[_\-/](\d{3,4})p(?:[_\-.?]|$)',
        text,
    )

    if match:

        try:
            return int(
                match.group(1)
            )
        except Exception:
            pass

    if "1080" in text:
        return 1080

    if "720" in text:
        return 720

    if "576" in text:
        return 576

    if "480" in text:
        return 480

    if "360" in text:
        return 360

    return 0


def score_stream(
    url,
    channel_key,
):

    score = 0

    lower = url.lower()

    quality = quality_from_url(url)

    if quality == 1080:
        score += 50

    elif quality == 720:
        score += 40

    elif quality == 576:
        score += 35

    elif quality == 480:
        score += 25

    elif quality == 360:
        score += 15

    # --------------------------------------------------------
    # NOW TV
    # --------------------------------------------------------

    if channel_key == "nowtv":

        if "nowtv-live-ad.ercdn.net" in lower:
            score += 30

        if "ciner-live.ercdn.net" in lower:
            score += 25

    # --------------------------------------------------------
    # SHOW TÜRK
    # --------------------------------------------------------

    if channel_key == "showturk":

        if "showturk" in lower:
            score += 30

        if "showturk-live" in lower:
            score += 35

    # --------------------------------------------------------
    # ALLGEMEIN
    # --------------------------------------------------------

    if "playlist.m3u8" in lower:
        score += 20

    if "master" in lower:
        score += 15

    if "index.m3u8" in lower:
        score += 10

    return score


# ============================================================
# STREAM VALIDIEREN
# ============================================================

def validate_stream(
    url,
    referer=None,
    timeout=5,
):

    if not is_valid_m3u8_url(url):
        return False

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )
    }

    if referer:
        headers["Referer"] = referer

    try:

        response = requests.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True,
        )

        if response.status_code != 200:
            return False

        content = response.text[:100000]

        if "#EXTM3U" in content:
            return True

    except Exception:
        pass

    return False


# ============================================================
# SEITENSCAN
# ============================================================

def scan_page(
    page,
    channel_key,
):

    candidates = []

    def add_urls(text):

        if not text:
            return

        for url in extract_m3u8(text):

            if not is_valid_m3u8_url(url):
                continue

            if not is_channel_stream(
                url,
                channel_key,
            ):
                continue

            if url not in candidates:
                candidates.append(url)

    # --------------------------------------------------------
    # PERFORMANCE
    # --------------------------------------------------------

    try:

        resources = page.evaluate(
            """
            () => performance
                .getEntriesByType('resource')
                .map(x => x.name)
            """
        )

        for resource in resources:
            add_urls(resource)

    except Exception:
        pass

    # --------------------------------------------------------
    # HTML
    # --------------------------------------------------------

    try:

        source = page.content()

        add_urls(source)
        add_urls(unquote(source))

    except Exception:
        pass

    # --------------------------------------------------------
    # SCRIPTS
    # --------------------------------------------------------

    try:

        scripts = page.locator(
            "script"
        ).all()

        for script in scripts:

            try:

                add_urls(
                    script.text_content()
                )

            except Exception:
                pass

            try:

                src = script.get_attribute(
                    "src"
                )

                if src:
                    add_urls(src)

            except Exception:
                pass

    except Exception:
        pass

    # --------------------------------------------------------
    # DATA-ATTRIBUTE
    # --------------------------------------------------------

    try:

        elements = page.locator(
            "[data-src], "
            "[data-url], "
            "[data-stream], "
            "[data-video], "
            "[data-player]"
        ).all()

        for element in elements:

            for attribute in (
                "data-src",
                "data-url",
                "data-stream",
                "data-video",
                "data-player",
            ):

                try:

                    value = element.get_attribute(
                        attribute
                    )

                    if value:
                        add_urls(value)

                except Exception:
                    pass

    except Exception:
        pass

    return candidates


# ============================================================
# BROWSER SCANNER
# ============================================================

def browser_find_stream(
    page,
    channel_key,
):

    channel = CHANNELS[channel_key]

    channel_url = channel["url"]

    candidates = []

    def add_candidate(url):

        url = normalize_url(url)

        if not url:
            return

        if not is_valid_m3u8_url(url):
            return

        if not is_channel_stream(
            url,
            channel_key,
        ):

            print(
                f"  Fremder Stream ignoriert: {url}"
            )

            return

        if url not in candidates:
            candidates.append(url)

    def capture_response(response):

        try:

            url = normalize_url(
                response.url
            )

            if ".m3u8" not in url.lower():
                return

            add_candidate(url)

        except Exception:
            pass

    page.on(
        "response",
        capture_response,
    )

    try:

        print(
            f"  Lade Seite: {channel_url}"
        )

        page.goto(
            channel_url,
            wait_until="domcontentloaded",
            timeout=30000,
        )

        page.wait_for_timeout(
            2500
        )

        start = time.monotonic()

        while (
            time.monotonic() - start
            < 10
        ):

            page.wait_for_timeout(
                500
            )

        if not candidates:

            print(
                "  Tiefer Seitenscan..."
            )

            for url in scan_page(
                page,
                channel_key,
            ):

                add_candidate(url)

    except Exception as exc:

        print(
            f"  Browser-Fehler: {exc}"
        )

        try:

            for url in scan_page(
                page,
                channel_key,
            ):

                add_candidate(url)

        except Exception:
            pass

    # --------------------------------------------------------
    # BESTEN STREAM ZUERST
    # --------------------------------------------------------

    candidates.sort(
        key=lambda x: score_stream(
            x,
            channel_key,
        ),
        reverse=True,
    )

    # --------------------------------------------------------
    # VALIDIEREN
    # --------------------------------------------------------

    valid = []

    for candidate in candidates:

        if not is_valid_m3u8_url(
            candidate
        ):
            continue

        if not is_channel_stream(
            candidate,
            channel_key,
        ):
            continue

        print(
            f"  Prüfe: {candidate}"
        )

        if validate_stream(
            candidate,
            referer=REFERERS[channel_key],
            timeout=5,
        ):

            valid.append(
                candidate
            )

            break

    return valid


# ============================================================
# FALLBACK
# ============================================================

def fallback_find(
    channel_key,
):

    candidates = FALLBACK_STREAMS.get(
        channel_key,
        [],
    )

    valid = []

    for url in candidates:

        if not is_valid_m3u8_url(url):
            continue

        if not is_channel_stream(
            url,
            channel_key,
        ):
            continue

        print(
            f"  Fallback prüfen: {url}"
        )

        if validate_stream(
            url,
            referer=REFERERS[channel_key],
            timeout=5,
        ):

            valid.append(url)

    return valid


# ============================================================
# STREAM-DATEI
# ============================================================

def write_channel_m3u(
    channel_key,
    streams,
):

    channel = CHANNELS[channel_key]

    path = os.path.join(
        STREAMS_DIR,
        f"{channel_key}.m3u",
    )

    lines = [
        "#EXTM3U"
    ]

    for stream in streams:

        if channel["tvg_id"]:

            extinf = (
                f'#EXTINF:-1 tvg-id="{channel["tvg_id"]}" '
                f'tvg-logo="{channel["logo"]}",'
                f'{channel["name"]}'
            )

        else:

            extinf = (
                f'#EXTINF:-1 '
                f'tvg-logo="{channel["logo"]}",'
                f'{channel["name"]}'
            )

        lines.append(extinf)
        lines.append(stream)

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as file:

        file.write(
            "\n".join(lines)
            + "\n"
        )


# ============================================================
# LINKS.TXT
# ============================================================

def write_links(
    all_streams,
):

    path = os.path.join(
        STREAMS_DIR,
        "links.txt",
    )

    lines = []

    for channel_key in (
        "nowtv",
        "showturk",
    ):

        channel = CHANNELS[channel_key]

        lines.append(
            f"### {channel['name']}"
        )

        lines.extend(
            all_streams.get(
                channel_key,
                []
            )
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

def playlist_channel_matches(
    extinf_line,
    channel_key,
):

    text = extinf_line.lower()

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
            or
            "show türk" in text
        )

    return False


# ============================================================
# HAUPTPLAYLIST AKTUALISIEREN
# ============================================================

def update_existing_playlist(
    channel_key,
    stream,
):

    if not os.path.exists(
        PLAYLIST_FILE
    ):

        print(
            f"Playlist nicht gefunden: "
            f"{PLAYLIST_FILE}"
        )

        return

    with open(
        PLAYLIST_FILE,
        "r",
        encoding="utf-8",
    ) as file:

        lines = file.readlines()

    found_channel = False

    for index in range(
        len(lines)
    ):

        line = lines[index]

        if not line.startswith(
            "#EXTINF"
        ):
            continue

        if not playlist_channel_matches(
            line,
            channel_key,
        ):
            continue

        found_channel = True

        print(
            f"  {CHANNELS[channel_key]['name']}-Eintrag gefunden:"
        )

        print(
            f"  {line.strip()}"
        )

        for next_index in range(
            index + 1,
            len(lines),
        ):

            candidate = (
                lines[next_index].strip()
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
                f"in Playlist aktualisiert."
            )

            print(
                f"  Neue URL: {stream}"
            )

            break

        break

    if not found_channel:

        print(
            f"  Kein "
            f"{CHANNELS[channel_key]['name']}-EXTINF-Eintrag "
            f"in der Playlist gefunden."
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
    message,
):

    channel = CHANNELS[channel_key]

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
            f"Status: {message}\n"
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
# EINEN KANAL SCANNEN
# ============================================================

def scan_channel(
    page,
    channel_key,
):

    channel = CHANNELS[channel_key]

    print()
    print("-" * 70)

    print(
        f"Kanal: {channel['name']}"
    )

    print(
        f"URL: {channel['url']}"
    )

    print("-" * 70)

    streams = []

    try:

        streams = browser_find_stream(
            page,
            channel_key,
        )

    except Exception as exc:

        print(
            f"  Scanner-Fehler: {exc}"
        )

    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------

    if not streams:

        print(
            "  Kein Stream über Webseite gefunden."
        )

        fallback = fallback_find(
            channel_key
        )

        if fallback:

            streams = fallback

            print(
                f"  Fallback erfolgreich: "
                f"{len(streams)} Stream(s)"
            )

    # --------------------------------------------------------
    # ERGEBNIS
    # --------------------------------------------------------

    if streams:

        unique = []

        for stream in streams:

            if stream not in unique:
                unique.append(stream)

        streams = unique

        print()
        print(
            f"  OK: {len(streams)} Stream(s)"
        )

        for stream in streams:

            print(
                f"  -> {stream}"
            )

        write_channel_m3u(
            channel_key,
            streams,
        )

        remove_error(
            channel_key
        )

        update_existing_playlist(
            channel_key,
            streams[0],
        )

    else:

        print()
        print(
            f"  FEHLER: "
            f"{channel['name']} M3U8 nicht gefunden"
        )

        write_error(
            channel_key,
            "M3U8 nicht gefunden",
        )

    return streams


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

    all_streams = {}

    with sync_playwright() as playwright:

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
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={
                "width": 1920,
                "height": 1080,
            },
            locale="de-DE",
            ignore_https_errors=True,
        )

        # ----------------------------------------------------
        # JE KANAL EIGENE PAGE
        # ----------------------------------------------------

        for channel_key in CHANNELS:

            page = context.new_page()

            # ------------------------------------------------
            # RESSOURCEN BLOCKIEREN
            # ------------------------------------------------

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

                streams = scan_channel(
                    page,
                    channel_key,
                )

                all_streams[
                    channel_key
                ] = streams

            except Exception as exc:

                print(
                    f"  Fehler bei "
                    f"{CHANNELS[channel_key]['name']}: "
                    f"{exc}"
                )

                all_streams[
                    channel_key
                ] = []

            try:
                page.close()
            except Exception:
                pass

        context.close()
        browser.close()

    # --------------------------------------------------------
    # LINKS.TXT
    # --------------------------------------------------------

    write_links(
        all_streams
    )

    # ========================================================
    # ABSCHLUSS
    # ========================================================

    successful = 0
    failed = 0

    for channel_key in CHANNELS:

        if all_streams.get(
            channel_key
        ):

            successful += 1

        else:

            failed += 1

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

    print(
        f"Playlist: {PLAYLIST_FILE}"
    )

    print(
        f"Streams:  {STREAMS_DIR}/"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()
