import os
import re
import time
import base64
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


# ============================================================
# KONFIGURATION
# ============================================================

NOW_URL = "https://www.nowtv.com.tr/canli-yayin"

OUTPUT_FILE = "streams/nowtv.m3u8"
ERROR_FILE = "streams/nowtv.error.txt"

REFERER = "https://www.nowtv.com.tr/"
ORIGIN = "https://www.nowtv.com.tr"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


# ============================================================
# REGEX
# ============================================================

M3U8_REGEX = re.compile(
    r'https?://[^\s"\'<>]+\.m3u8(?:\?[^\s"\'<>]*)?',
    re.IGNORECASE
)

RELATIVE_M3U8_REGEX = re.compile(
    r'["\']([^"\']+\.m3u8(?:\?[^"\']*)?)["\']',
    re.IGNORECASE
)


# ============================================================
# URL NORMALISIEREN
# ============================================================

def normalize_url(url, base_url=None):

    if not url:
        return None

    url = url.strip().strip('"\'')
    url = url.replace("\\/", "/")

    if url.startswith("//"):
        return "https:" + url

    if url.startswith(("http://", "https://")):
        return url

    if not base_url:
        return None

    parsed = urlparse(base_url)

    if url.startswith("/"):
        return (
            f"{parsed.scheme}://"
            f"{parsed.netloc}"
            f"{url}"
        )

    base = base_url.rsplit("/", 1)[0] + "/"

    return base + url


# ============================================================
# BASE64
# ============================================================

def decode_base64(value):

    try:

        value += "=" * (-len(value) % 4)

        return base64.b64decode(
            value
        ).decode(
            "utf-8",
            errors="ignore"
        )

    except Exception:

        return ""


# ============================================================
# M3U8 AUS TEXT EXTRAHIEREN
# ============================================================

def extract_m3u8(text, base_url=None):

    if not text:
        return []

    found = []

    # Absolute M3U8 URLs
    for match in M3U8_REGEX.findall(text):

        url = normalize_url(
            match,
            base_url
        )

        if url:
            found.append(url)

    # Relative M3U8 URLs
    for match in RELATIVE_M3U8_REGEX.findall(text):

        url = normalize_url(
            match,
            base_url
        )

        if url:
            found.append(url)

    # Base64 kodierte M3U8 URLs
    for token in re.findall(
        r'["\']([A-Za-z0-9+/=_-]{40,})["\']',
        text
    ):

        decoded = decode_base64(token)

        if ".m3u8" in decoded.lower():

            for match in M3U8_REGEX.findall(
                decoded
            ):

                url = normalize_url(
                    match,
                    base_url
                )

                if url:
                    found.append(url)

    return list(
        dict.fromkeys(found)
    )


# ============================================================
# TOKEN
# ============================================================

def get_expiration(url):

    match = re.search(
        r"(?:[?&])e=(\d+)",
        url
    )

    if not match:
        return None

    try:
        return int(match.group(1))
    except Exception:
        return None


def token_remaining(url):

    expiration = get_expiration(url)

    if expiration is None:
        return -1

    return expiration - int(time.time())


def has_token(url):

    return (
        re.search(
            r"(?:[?&])st=[^&]+",
            url
        )
        is not None
        and
        re.search(
            r"(?:[?&])e=\d+",
            url
        )
        is not None
    )


# ============================================================
# IST DIE GEWÜNSCHTE NOW-TV MASTER-PLAYLIST?
# ============================================================

def is_nowtv_playlist(url):

    lower = url.lower()

    return (
        "nowtv-live-ad.ercdn.net" in lower
        and
        "/nowtv/playlist.m3u8" in lower
        and
        has_token(url)
    )


# ============================================================
# HLS VALIDIEREN
# ============================================================

def validate_stream(
    url,
    request_context
):

    try:

        response = request_context.get(
            url,
            timeout=15000,
            headers={
                "User-Agent": USER_AGENT,
                "Referer": REFERER,
                "Origin": ORIGIN,
                "Accept": (
                    "application/vnd.apple.mpegurl,"
                    "application/x-mpegURL,"
                    "application/octet-stream,"
                    "*/*"
                ),
            },
        )

        print(
            f"[NOW TV] HTTP {response.status}"
        )

        if response.status != 200:
            return False

        content_type = (
            response.headers
            .get("content-type", "")
            .lower()
        )

        if (
            "mpegurl" in content_type
            or "m3u8" in content_type
        ):
            return True

        try:

            body = response.text()

            if "#EXTM3U" in body:
                return True

            if "#EXT-X-" in body:
                return True

        except Exception:
            pass

    except Exception as e:

        print(
            f"[NOW TV] Validierungsfehler: {e}"
        )

    return False


# ============================================================
# SEITE SCANNEN
# ============================================================

def scan_page(page):

    urls = []

    # --------------------------------------------------------
    # Browser Performance
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

            urls.extend(
                extract_m3u8(
                    resource,
                    page.url
                )
            )

    except Exception:
        pass

    # --------------------------------------------------------
    # HTML
    # --------------------------------------------------------

    try:

        html = page.content()

        urls.extend(
            extract_m3u8(
                html,
                page.url
            )
        )

    except Exception:
        pass

    # --------------------------------------------------------
    # Frames
    # --------------------------------------------------------

    for frame in page.frames:

        try:

            html = frame.content()

            urls.extend(
                extract_m3u8(
                    html,
                    frame.url
                )
            )

        except Exception:
            pass

        try:

            resources = frame.evaluate(
                """
                () => performance
                    .getEntriesByType('resource')
                    .map(x => x.name)
                """
            )

            for resource in resources:

                urls.extend(
                    extract_m3u8(
                        resource,
                        frame.url
                    )
                )

        except Exception:
            pass

    return list(
        dict.fromkeys(urls)
    )


# ============================================================
# BROWSER SCAN
# ============================================================

def browser_find_stream(browser):

    print("")
    print("======================================")
    print("         NOW TV SCAN")
    print("======================================")

    context = browser.new_context(
        user_agent=USER_AGENT,
        locale="tr-TR",
        timezone_id="Europe/Istanbul",
        ignore_https_errors=True,
    )

    page = context.new_page()

    discovered = []

    # --------------------------------------------------------
    # Netzwerk direkt beobachten
    # --------------------------------------------------------

    def on_response(response):

        try:

            url = response.url

            if ".m3u8" in url.lower():

                if url not in discovered:

                    discovered.append(url)

                    print("")
                    print(
                        "[NOW TV] M3U8 RESPONSE:"
                    )
                    print(url)

        except Exception:
            pass

    page.on(
        "response",
        on_response
    )

    try:

        print(
            f"[NOW TV] Öffne: {NOW_URL}"
        )

        page.goto(
            NOW_URL,
            wait_until="domcontentloaded",
            timeout=30000,
        )

        # ----------------------------------------------------
        # Erste Netzwerkaktivität
        # ----------------------------------------------------

        page.wait_for_timeout(4000)

        discovered.extend(
            scan_page(page)
        )

        # ----------------------------------------------------
        # Video starten
        # ----------------------------------------------------

        try:

            page.evaluate(
                """
                () => {
                    document
                        .querySelectorAll('video')
                        .forEach(video => {
                            try {
                                video.muted = true;
                                video.play().catch(() => {});
                            } catch(e) {}
                        });
                }
                """
            )

        except Exception:
            pass

        # ----------------------------------------------------
        # Weitere Netzwerkaktivität
        # ----------------------------------------------------

        for _ in range(10):

            page.wait_for_timeout(2000)

            discovered.extend(
                scan_page(page)
            )

            discovered = list(
                dict.fromkeys(discovered)
            )

            # Sobald eine signierte Master-Playlist
            # gefunden wurde, noch kurz weiterlaufen,
            # damit wir sicher den aktuellen Token haben.

            masters = [
                url
                for url in discovered
                if is_nowtv_playlist(url)
            ]

            if masters:

                print("")
                print(
                    "[NOW TV] ✓ Signierte "
                    "playlist.m3u8 gefunden."
                )

                # Noch kurz warten, falls eine neuere
                # Token-URL auftaucht.
                page.wait_for_timeout(1000)

                discovered.extend(
                    scan_page(page)
                )

                break

    except Exception as e:

        print(
            f"[NOW TV] Browser-Fehler: {e}"
        )

    finally:

        context.close()

    return list(
        dict.fromkeys(discovered)
    )


# ============================================================
# BESTE URL AUSWÄHLEN
# ============================================================

def choose_stream(
    urls,
    request_context
):

    if not urls:
        return None

    print("")
    print("======================================")
    print("       GEFUNDENE NOW TV URLS")
    print("======================================")

    for url in urls:

        print(url)

    # ========================================================
    # 1. ABSOLUTE PRIORITÄT:
    #
    # nowtv-live-ad.ercdn.net/nowtv/playlist.m3u8
    # mit st + e
    # ========================================================

    master_urls = [
        url
        for url in urls
        if is_nowtv_playlist(url)
    ]

    # Neuester Token zuerst
    master_urls.sort(
        key=token_remaining,
        reverse=True
    )

    print("")
    print("======================================")
    print(" SIGNIERTE NOW TV MASTER PLAYLISTS")
    print("======================================")

    for url in master_urls:

        print(
            f"Token: {token_remaining(url)} Sekunden"
        )

        print(url)

    # ========================================================
    # Master Playlist validieren
    # ========================================================

    for url in master_urls:

        print("")
        print(
            "[NOW TV] Prüfe MASTER:"
        )
        print(url)

        if validate_stream(
            url,
            request_context
        ):

            print("")
            print(
                "======================================"
            )
            print(
                "✓ NOW TV MASTER PLAYLIST GEFUNDEN"
            )
            print(
                "======================================"
            )
            print(url)

            return url

    # ========================================================
    # FALLBACK:
    # Andere tokenisierte NOW-TV-Streams
    # ========================================================

    other_tokenized = [
        url
        for url in urls
        if (
            has_token(url)
            and
            (
                "nowtv-live-ad.ercdn.net" in url.lower()
                or "ercdn.net" in url.lower()
            )
        )
    ]

    other_tokenized.sort(
        key=token_remaining,
        reverse=True
    )

    for url in other_tokenized:

        print("")
        print(
            "[NOW TV] Prüfe alternative "
            "tokenisierte URL:"
        )
        print(url)

        if validate_stream(
            url,
            request_context
        ):

            print(
                "[NOW TV] ✓ Alternative URL gültig."
            )

            return url

    return None


# ============================================================
# FALLBACK
# ============================================================

def fallback_find(
    request_context
):

    print("")
    print("======================================")
    print("          NOW TV FALLBACK")
    print("======================================")

    # Dieser Fallback ist nur die bekannte
    # ungetokenisierte Master-URL.
    #
    # Wenn NOW TV einen Token verlangt,
    # kann diese URL 403 liefern.

    url = (
        "https://nowtv-live-ad.ercdn.net/"
        "nowtv/playlist.m3u8"
    )

    print(
        "[NOW TV] Fallback:"
    )
    print(url)

    if validate_stream(
        url,
        request_context
    ):

        return url

    return None


# ============================================================
# M3U8 SCHREIBEN
# ============================================================

def write_nowtv(stream_url):

    os.makedirs(
        "streams",
        exist_ok=True
    )

    # EXAKT der Dateiname aus deiner YAML
    path = OUTPUT_FILE

    content = (
        "#EXTM3U\n"
        '#EXTINF:-1 tvg-id="nowtv" '
        'tvg-name="NOW TV" '
        'group-title="Turkiye",NOW TV\n'
        f"{stream_url}\n"
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(content)

    print("")
    print("======================================")
    print("       NOWTV.M3U8 GESCHRIEBEN")
    print("======================================")
    print(content)


# ============================================================
# ERROR
# ============================================================

def write_error(message):

    os.makedirs(
        "streams",
        exist_ok=True
    )

    with open(
        ERROR_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            message + "\n"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print("")
    print("======================================")
    print("       NOW TV STREAM SCANNER")
    print("======================================")

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )

        request_context = (
            p.request.new_context(
                user_agent=USER_AGENT,
                ignore_https_errors=True,
            )
        )

        try:

            # ------------------------------------------------
            # NOW TV scannen
            # ------------------------------------------------

            urls = browser_find_stream(
                browser
            )

            urls = list(
                dict.fromkeys(urls)
            )

            print("")
            print(
                f"[NOW TV] "
                f"{len(urls)} M3U8 URL(s) gefunden."
            )

            # ------------------------------------------------
            # Gewünschte Master Playlist auswählen
            # ------------------------------------------------

            stream = choose_stream(
                urls,
                request_context
            )

            # ------------------------------------------------
            # Fallback
            # ------------------------------------------------

            if not stream:

                stream = fallback_find(
                    request_context
                )

            # ------------------------------------------------
            # ERFOLG
            # ------------------------------------------------

            if stream:

                write_nowtv(
                    stream
                )

                if os.path.exists(
                    ERROR_FILE
                ):

                    os.remove(
                        ERROR_FILE
                    )

                print("")
                print(
                    "✓ NOW TV erfolgreich aktualisiert."
                )

            # ------------------------------------------------
            # FEHLER
            # ------------------------------------------------

            else:

                message = (
                    "Keine gültige NOW TV "
                    "playlist.m3u8 gefunden."
                )

                write_error(
                    message
                )

                print("")
                print(
                    f"✗ {message}"
                )

                # Vorhandene nowtv.m3u8 NICHT löschen.
                # So bleibt die letzte funktionierende
                # Version erhalten.

        finally:

            request_context.dispose()
            browser.close()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()
