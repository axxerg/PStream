import os
import re
import time
import base64
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


# ============================================================
# NOW TV
# ============================================================

CHANNEL = {
    "id": "nowtv",
    "name": "NOW TV",
    "url": "https://www.nowtv.com.tr/canli-yayin",
}

REFERER = "https://www.nowtv.com.tr/"

ORIGIN = "https://www.nowtv.com.tr"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

# ZIELDATEI
OUTPUT_FILE = "streams/nowtv.m3u8"

ERROR_FILE = "streams/nowtv.error.txt"


# ============================================================
# REGEX
# ============================================================

STREAM_REGEX = re.compile(
    r'https?://[^\s"\'<>]+\.m3u8(?:\?[^\s"\'<>]*)?',
    re.IGNORECASE
)

RELATIVE_M3U8_REGEX = re.compile(
    r'["\']([^"\']+\.m3u8(?:\?[^"\']*)?)["\']',
    re.IGNORECASE
)


# ============================================================
# URL
# ============================================================

def normalize_url(url, base_url=None):

    if not url:
        return None

    url = url.strip().strip('"\'')
    url = url.replace("\\/", "/")

    if url.startswith("//"):
        url = "https:" + url

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
# M3U8 EXTRACT
# ============================================================

def extract_m3u8(text, base_url=None):

    if not text:
        return []

    found = []

    # Absolute URLs
    for match in STREAM_REGEX.findall(text):

        url = normalize_url(
            match,
            base_url
        )

        if url:
            found.append(url)

    # Relative URLs
    for match in RELATIVE_M3U8_REGEX.findall(text):

        url = normalize_url(
            match,
            base_url
        )

        if url:
            found.append(url)

    # Base64 URLs
    for token in re.findall(
        r'["\']([A-Za-z0-9+/=_-]{40,})["\']',
        text
    ):

        decoded = decode_base64(token)

        if ".m3u8" in decoded.lower():

            for match in STREAM_REGEX.findall(
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
# HLS VALIDIERUNG
# ============================================================

def is_hls_response(response):

    try:

        content_type = (
            response.headers
            .get("content-type", "")
            .lower()
        )

        if (
            "mpegurl" in content_type
            or "vnd.apple.mpegurl" in content_type
            or "application/x-mpegurl" in content_type
            or "m3u8" in content_type
        ):
            return True

        body = response.text()

        if "#EXTM3U" in body:
            return True

        if "#EXT-X-" in body:
            return True

    except Exception:
        pass

    return False


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

        return is_hls_response(
            response
        )

    except Exception as e:

        print(
            f"[NOW TV] Stream-Kontrolle: {e}"
        )

        return False


# ============================================================
# TOKEN RESTZEIT
# ============================================================

def token_remaining_seconds(url):

    match = re.search(
        r"(?:[?&])e=(\d+)",
        url
    )

    if not match:
        return 999999999

    try:

        expires = int(
            match.group(1)
        )

        return expires - int(
            time.time()
        )

    except Exception:

        return 0


# ============================================================
# SEITE SCANNEN
# ============================================================

def scan_page(page):

    urls = []

    # --------------------------------------------------------
    # Performance
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

            frame_html = frame.content()

            urls.extend(
                extract_m3u8(
                    frame_html,
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
    print("NOW TV SCAN")
    print("======================================")

    context = browser.new_context(
        user_agent=USER_AGENT,
        locale="tr-TR",
        timezone_id="Europe/Istanbul",
        ignore_https_errors=True,
    )

    page = context.new_page()

    discovered = []

    try:

        print(
            f"[NOW TV] Öffne: {CHANNEL['url']}"
        )

        page.goto(
            CHANNEL["url"],
            wait_until="domcontentloaded",
            timeout=30000,
        )

        # Erste Requests
        page.wait_for_timeout(3000)

        discovered.extend(
            scan_page(page)
        )

        # Video starten
        try:

            page.evaluate(
                """
                () => {
                    document
                        .querySelectorAll('video')
                        .forEach(v => {
                            try {
                                v.muted = true;
                                v.play().catch(() => {});
                            } catch(e) {}
                        });
                }
                """
            )

        except Exception:
            pass

        # Weitere Netzwerkaktivität abwarten
        for _ in range(5):

            page.wait_for_timeout(2000)

            discovered.extend(
                scan_page(page)
            )

            discovered = list(
                dict.fromkeys(discovered)
            )

            if discovered:
                print(
                    f"[NOW TV] "
                    f"{len(discovered)} M3U8 gefunden."
                )

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
# BESTEN STREAM AUSWÄHLEN
# ============================================================

def pick_best_stream(
    urls,
    request_context
):

    if not urls:
        return None

    # NOW TV CDN bevorzugen
    preferred = []

    for url in urls:

        lower = url.lower()

        if (
            "nowtv" in lower
            or "ercdn.net" in lower
        ):
            preferred.append(url)

    if preferred:
        urls = preferred

    # Längste Token-Laufzeit zuerst
    urls = sorted(
        urls,
        key=token_remaining_seconds,
        reverse=True
    )

    print("")
    print(
        "[NOW TV] Gefundene Streams:"
    )

    for url in urls:

        remaining = token_remaining_seconds(
            url
        )

        print(
            f"  {remaining}s -> {url}"
        )

    # Validieren
    for url in urls:

        print("")
        print(
            "[NOW TV] Prüfe:"
        )
        print(url)

        if validate_stream(
            url,
            request_context
        ):

            print(
                "[NOW TV] ✓ HLS Stream gültig."
            )

            return url

    return None


# ============================================================
# FALLBACK
# ============================================================

FALLBACK_STREAMS = [
    "https://nowtv-live-ad.ercdn.net/nowtv/playlist.m3u8",
]


def fallback_find(
    request_context
):

    print("")
    print(
        "[NOW TV] Fallback wird geprüft..."
    )

    for url in FALLBACK_STREAMS:

        if validate_stream(
            url,
            request_context
        ):

            print(
                "[NOW TV] ✓ Fallback funktioniert:"
            )

            print(url)

            return url

    return None


# ============================================================
# NOWTV.M3U8 SCHREIBEN
# ============================================================

def write_nowtv(stream_url):

    os.makedirs(
        "streams",
        exist_ok=True
    )

    # WICHTIG:
    # Genau derselbe Dateiname wie in YAML.
    path = "streams/nowtv.m3u8"

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
    print("NOW TV.M3U8 ERSTELLT")
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
            # Browser Scan
            # ------------------------------------------------

            urls = browser_find_stream(
                browser
            )

            print("")
            print(
                f"[NOW TV] "
                f"{len(urls)} Stream(s) gefunden."
            )

            # ------------------------------------------------
            # Besten Stream wählen
            # ------------------------------------------------

            stream = pick_best_stream(
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
            # Erfolgreich
            # ------------------------------------------------

            if stream:

                write_nowtv(
                    stream
                )

                # Fehlerdatei löschen
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
            # Kein Stream
            # ------------------------------------------------

            else:

                message = (
                    "NOW TV Stream wurde "
                    "nicht gefunden oder "
                    "konnte nicht validiert werden."
                )

                write_error(
                    message
                )

                print("")
                print(
                    f"✗ {message}"
                )

                # Vorhandene nowtv.m3u8 NICHT löschen.
                # So bleibt der letzte funktionierende
                # Stream erhalten.

        finally:

            request_context.dispose()
            browser.close()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()
