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
    "showturk": {
        "name": "ShowTurk",
        "url": "https://www.showturk.com.tr/canli-yayin",
    },
    "nowtv": {
        "name": "NOW TV",
        "url": "https://www.nowtv.com.tr/canli-yayin",
    },
}


# ============================================================
# FALLBACK-STREAMS
# ============================================================

FALLBACK_STREAMS = {
    "showturk": [
        "https://ciner-live.ercdn.net/showturk/playlist.m3u8",
    ],

    "nowtv": [
        "https://ciner-live.ercdn.net/nowtv/playlist.m3u8",
    ],
}


# ============================================================
# REFERER
# ============================================================

REFERERS = {
    "showturk": "https://www.showturk.com.tr/",
    "nowtv": "https://www.nowtv.com.tr/",
}


# ============================================================
# HILFSFUNKTIONEN
# ============================================================

def ensure_directories():
    os.makedirs(STREAMS_DIR, exist_ok=True)

    playlist_dir = os.path.dirname(PLAYLIST_FILE)

    if playlist_dir:
        os.makedirs(playlist_dir, exist_ok=True)


def normalize_url(url):

    if not url:
        return ""

    url = html.unescape(url)

    url = url.replace("\\/", "/")
    url = url.replace("\\u0026", "&")
    url = url.replace("\\u003d", "=")
    url = url.replace("\\u003F", "?")
    url = url.replace("\\u003f", "?")

    return url.strip().strip('"').strip("'")


def extract_urls(text):

    if not text:
        return []

    found = []

    patterns = [
        r'https?://[^"\'>\s\\]+\.m3u8(?:\?[^"\'>\s\\]*)?',
        r'https?%3A%2F%2F[^"\'>\s\\]+%2Em3u8[^"\'>\s\\]*',
    ]

    for pattern in patterns:

        for match in re.findall(
            pattern,
            text,
            flags=re.IGNORECASE,
        ):

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

        params = parse_qs(parsed.query)

        if "e" not in params:
            return False

        expiry = int(params["e"][0])

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
# SENDER-FILTER
# ============================================================

def is_channel_stream(channel_id, url):

    url = url.lower()

    if channel_id == "showturk":

        return (
            "ciner-live.ercdn.net/showturk" in url
            or "showturk" in url
        )

    if channel_id == "nowtv":

        return (
            "nowtv-live-ad.ercdn.net/nowtv" in url
            or "ciner-live.ercdn.net/nowtv" in url
            or "nowtv" in url
        )

    return False


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

def scan_page(page):

    candidates = []

    def add_urls(text):

        if not text:
            return

        for url in extract_m3u8(text):

            if (
                is_valid_m3u8_url(url)
                and url not in candidates
            ):

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

        scripts = page.locator("script").all()

        for script in scripts:

            try:
                add_urls(script.text_content())
            except Exception:
                pass

            try:

                src = script.get_attribute("src")

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
    channel_id,
    channel_url,
):

    candidates = []

    gefunden = False

    def add_candidate(url):

        nonlocal candidates

        url = normalize_url(url)

        if not url:
            return

        if not is_valid_m3u8_url(url):
            return

        if not is_channel_stream(
            channel_id,
            url,
        ):

            print(
                f"  Falscher Stream ignoriert: {url}"
            )

            return

        if url not in candidates:
            candidates.append(url)

    def capture_response(response):

        nonlocal gefunden

        try:

            url = normalize_url(
                response.url
            )

            if ".m3u8" not in url.lower():
                return

            add_candidate(url)

            if candidates:
                gefunden = True

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

        page.wait_for_timeout(1500)

        start = time.monotonic()

        while (
            time.monotonic() - start < 10
        ):

            if gefunden:
                break

            page.wait_for_timeout(500)

        if not candidates:

            print(
                "  Tiefer Seitenscan..."
            )

            for url in scan_page(page):

                add_candidate(url)

    except Exception as exc:

        print(
            f"  Browser-Fehler: {exc}"
        )

        try:

            for url in scan_page(page):
                add_candidate(url)

        except Exception:
            pass

    # --------------------------------------------------------
    # Sortierung
    # --------------------------------------------------------

    candidates.sort(
        key=lambda x: (
            0 if "720p" in x.lower() else 1
        )
    )

    # --------------------------------------------------------
    # Validieren
    # --------------------------------------------------------

    referer = REFERERS.get(channel_id)

    valid = []

    for candidate in candidates:

        if not is_valid_m3u8_url(candidate):
            continue

        if not is_channel_stream(
            channel_id,
            candidate,
        ):
            continue

        print(
            f"  Prüfe: {candidate}"
        )

        if validate_stream(
            candidate,
            referer=referer,
            timeout=5,
        ):

            valid.append(candidate)

            break

    return valid


# ============================================================
# FALLBACK
# ============================================================

def fallback_find(channel_id):

    candidates = FALLBACK_STREAMS.get(
        channel_id,
        [],
    )

    valid = []

    for url in candidates:

        if not is_valid_m3u8_url(url):
            continue

        if not is_channel_stream(
            channel_id,
            url,
        ):
            continue

        print(
            f"  Fallback prüfen: {url}"
        )

        if validate_stream(
            url,
            referer=REFERERS.get(channel_id),
            timeout=5,
        ):

            valid.append(url)

    return valid


# ============================================================
# STREAM-DATEIEN
# ============================================================

def write_channel_m3u(
    channel_id,
    channel,
    streams,
):

    path = os.path.join(
        STREAMS_DIR,
        f"{channel_id}.m3u",
    )

    lines = ["#EXTM3U"]

    for stream in streams:

        lines.append(
            f'#EXTINF:-1 tvg-id="{channel_id}" '
            f'tvg-name="{channel["name"]}",'
            f'{channel["name"]}'
        )

        lines.append(stream)

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as file:

        file.write(
            "\n".join(lines) + "\n"
        )


def write_all_m3u(results):

    path = os.path.join(
        STREAMS_DIR,
        "all.m3u",
    )

    lines = ["#EXTM3U"]

    for channel_id, streams in results.items():

        channel = CHANNELS[channel_id]

        for stream in streams:

            lines.append(
                f'#EXTINF:-1 tvg-id="{channel_id}" '
                f'tvg-name="{channel["name"]}",'
                f'{channel["name"]}'
            )

            lines.append(stream)

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as file:

        file.write(
            "\n".join(lines) + "\n"
        )


def write_links(results):

    path = os.path.join(
        STREAMS_DIR,
        "links.txt",
    )

    lines = []

    for channel_id, streams in results.items():

        channel = CHANNELS[channel_id]

        lines.append(
            f"### {channel['name']}"
        )

        for stream in streams:
            lines.append(stream)

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
# PLAYLIST MATCHING
# ============================================================

def playlist_channel_matches(
    extinf_line,
    channel_id,
):

    text = extinf_line.lower()

    if channel_id == "showturk":

        return (
            "showturk" in text
            or "show türk" in text
        )

    if channel_id == "nowtv":

        return (
            "now tv" in text
            or "nowtv" in text
        )

    return False


# ============================================================
# HAUPT-PLAYLIST AKTUALISIEREN
# ============================================================

def update_existing_playlist(results):

    if not os.path.exists(PLAYLIST_FILE):

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

    for channel_id, streams in results.items():

        if not streams:
            continue

        replacement = streams[0]

        found_channel = False

        for index in range(len(lines)):

            line = lines[index]

            if not line.startswith("#EXTINF"):
                continue

            if not playlist_channel_matches(
                line,
                channel_id,
            ):
                continue

            found_channel = True

            for next_index in range(
                index + 1,
                len(lines),
            ):

                candidate = lines[next_index].strip()

                if not candidate:
                    continue

                if candidate.startswith("#"):
                    continue

                lines[next_index] = (
                    replacement + "\n"
                )

                break

            break

        if not found_channel:

            print(
                f"  Kein EXTINF-Eintrag gefunden: "
                f"{CHANNELS[channel_id]['name']}"
            )

    with open(
        PLAYLIST_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        file.writelines(lines)


# ============================================================
# FEHLERDATEI
# ============================================================

def write_error(
    channel_id,
    message,
):

    path = os.path.join(
        STREAMS_DIR,
        f"{channel_id}_error.txt",
    )

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as file:

        file.write(
            f"Kanal: {CHANNELS[channel_id]['name']}\n"
        )

        file.write(
            f"URL: {CHANNELS[channel_id]['url']}\n"
        )

        file.write(
            f"Status: {message}\n"
        )


def remove_error(channel_id):

    path = os.path.join(
        STREAMS_DIR,
        f"{channel_id}_error.txt",
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

    results = {}

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

        page = context.new_page()

        # ----------------------------------------------------
        # Ressourcen blockieren
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # NUR 2 SENDER
        # ----------------------------------------------------

        for channel_id, channel in CHANNELS.items():

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
                    channel_id,
                    channel["url"],
                )

            except Exception as exc:

                print(
                    f"  Scanner-Fehler: {exc}"
                )

            # ------------------------------------------------
            # FALLBACK
            # ------------------------------------------------

            if not streams:

                print(
                    "  Kein Stream über Webseite gefunden."
                )

                fallback = fallback_find(
                    channel_id
                )

                if fallback:

                    streams = fallback

                    print(
                        f"  Fallback erfolgreich: "
                        f"{len(streams)} Stream(s)"
                    )

            # ------------------------------------------------
            # ERGEBNIS
            # ------------------------------------------------

            if streams:

                unique = []

                for stream in streams:

                    if stream not in unique:
                        unique.append(stream)

                streams = unique

                results[channel_id] = streams

                print()
                print(
                    f"  OK: {len(streams)} Stream(s)"
                )

                for stream in streams:
                    print(
                        f"  -> {stream}"
                    )

                write_channel_m3u(
                    channel_id,
                    channel,
                    streams,
                )

                remove_error(channel_id)

            else:

                results[channel_id] = []

                print()
                print(
                    "  FEHLER: M3U8 nicht gefunden"
                )

                write_error(
                    channel_id,
                    "M3U8 nicht gefunden",
                )

        context.close()
        browser.close()

    # ========================================================
    # GESAMTDATEIEN
    # ========================================================

    write_all_m3u(results)
    write_links(results)

    # ========================================================
    # HAUPT-PLAYLIST
    # ========================================================

    print()
    print("=" * 70)
    print("HAUPT-PLAYLIST AKTUALISIEREN")
    print("=" * 70)

    update_existing_playlist(results)

    # ========================================================
    # ABSCHLUSS
    # ========================================================

    erfolgreich = sum(
        1
        for streams in results.values()
        if streams
    )

    fehler = len(CHANNELS) - erfolgreich

    print()
    print("=" * 70)
    print("SCAN ABGESCHLOSSEN")
    print("=" * 70)

    print(
        f"Erfolgreich: {erfolgreich}/{len(CHANNELS)}"
    )

    print(
        f"Fehler:      {fehler}/{len(CHANNELS)}"
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
