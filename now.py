import os
import re
import time
import base64
from urllib.parse import urljoin

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


# ============================================================
# REGEX
# ============================================================

ABSOLUTE_M3U8_REGEX = re.compile(
    r'https?://[^\s"\'<>]+\.m3u8(?:\?[^\s"\'<>]*)?',
    re.IGNORECASE,
)

ANY_M3U8_REGEX = re.compile(
    r'["\']([^"\']*\.m3u8(?:\?[^"\']*)?)["\']',
    re.IGNORECASE,
)


# ============================================================
# URL HILFSFUNKTIONEN
# ============================================================

def normalize_url(url, base_url=None):
    if not url:
        return None

    url = url.strip().strip("\"'")
    url = url.replace("\\/", "/")

    if url.startswith("//"):
        url = "https:" + url

    if base_url:
        url = urljoin(base_url, url)

    return url


def decode_base64(value):
    try:
        value += "=" * (-len(value) % 4)
        return base64.b64decode(value).decode(
            "utf-8",
            errors="ignore"
        )
    except Exception:
        return ""


# ============================================================
# M3U8 ERKENNUNG
# ============================================================

def extract_m3u8(text, base_url=None):
    if not text:
        return []

    found = []

    # Absolute URLs
    for match in ABSOLUTE_M3U8_REGEX.findall(text):
        url = normalize_url(match, base_url)

        if url:
            found.append(url)

    # Relative URLs
    for match in ANY_M3U8_REGEX.findall(text):
        url = normalize_url(match, base_url)

        if url:
            found.append(url)

    # Base64 versteckte URLs
    for token in re.findall(
        r'["\']([A-Za-z0-9+/=_-]{40,})["\']',
        text
    ):
        decoded = decode_base64(token)

        if ".m3u8" in decoded.lower():

            for match in ABSOLUTE_M3U8_REGEX.findall(decoded):

                url = normalize_url(
                    match,
                    base_url
                )

                if url:
                    found.append(url)

    return list(dict.fromkeys(found))


# ============================================================
# HLS KONTROLLE
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


def validate_stream(url, request_context):

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
            f"[NOW TV] HTTP {response.status}: {url}"
        )

        if response.status != 200:
            return False

        return is_hls_response(response)

    except Exception as e:

        print(
            f"[NOW TV] Streamkontrolle Fehler: {e}"
        )

        return False


# ============================================================
# TOKEN
# ============================================================

def token_remaining_seconds(url):

    match = re.search(
        r"(?:[?&])e=(\d+)",
        url
    )

    if not match:
        return 999999999

    try:

        expires = int(match.group(1))

        return expires - int(time.time())

    except Exception:

        return 0


# ============================================================
# MASTER PLAYLIST PRIORISIEREN
# ============================================================

def is_master_playlist(url):

    lower = url.lower()

    # Genau die gewünschte NOW-TV Masterplaylist
    if (
        "nowtv-live-ad.ercdn.net" in lower
        and "/nowtv/playlist.m3u8" in lower
    ):
        return True

    return False


def stream_score(url):

    lower = url.lower()

    score = 0

    # Höchste Priorität:
    # NOW TV Masterplaylist
    if is_master_playlist(url):
        score += 10000

    # NOW TV CDN
    if "nowtv-live-ad.ercdn.net" in lower:
        score += 5000

    # Signierter Stream
    if "st=" in lower:
        score += 1000

    if "e=" in lower:
        score += 1000

    # Masterplaylist zusätzlich bevorzugen
    if "/playlist.m3u8" in lower:
        score += 3000

    # Direkte Qualitätsstreams niedriger bewerten
    if re.search(
        r"nowtv_(360p|480p|720p|1080p)\.m3u8",
        lower
    ):
        score -= 500

    # Gültigkeitsdauer berücksichtigen
    remaining = token_remaining_seconds(url)

    if remaining > 0:
        score += min(
            remaining,
            3600
        )

    return score


# ============================================================
# SEITE SCANNEN
# ============================================================

def scan_page(page):

    urls = []

    # Browser Resources
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

    # HTML
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

    # Frames
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

    return list(dict.fromkeys(urls))


# ============================================================
# BROWSER
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

    # Netzwerk direkt beobachten
    def handle_response(response):

        try:

            url = response.url

            if ".m3u8" in url.lower():

                discovered.append(url)

                print(
                    f"[NOW TV] M3U8 entdeckt:\n{url}"
                )

        except Exception:
            pass

    page.on(
        "response",
        handle_response
    )

    try:

        print(
            f"[NOW TV] Öffne: {CHANNEL['url']}"
        )

        page.goto(
            CHANNEL["url"],
            wait_until="domcontentloaded",
            timeout=30000,
        )

        # Etwas Zeit für den Player
        page.wait_for_timeout(4000)

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
        for _ in range(6):

            page.wait_for_timeout(2000)

            discovered.extend(
                scan_page(page)
            )

    except Exception as e:

        print(
            f"[NOW TV] Browserfehler: {e}"
        )

    finally:

        context.close()

    return list(
        dict.fromkeys(discovered)
    )


# ============================================================
# BESTEN STREAM AUSWÄHLEN
# ============================================================

def pick_best_stream(urls, request_context):

    if not urls:
        return None

    # Nur NOW-TV-relevante URLs
    now_urls = []

    for url in urls:

        lower = url.lower()

        if (
            "nowtv-live-ad.ercdn.net" in lower
            or "nowtv" in lower
        ):
            now_urls.append(url)

    if now_urls:
        urls = now_urls

    # Masterplaylist zuerst
    urls = sorted(
        urls,
        key=stream_score,
        reverse=True,
    )

    print("")
    print("======================================")
    print("GEFUNDENE NOW-TV STREAMS")
    print("======================================")

    for url in urls:

        remaining = token_remaining_seconds(
            url
        )

        print(
            f"{remaining}s | "
            f"{stream_score(url)} Punkte | "
            f"{url}"
        )

    # ZUERST Masterplaylist versuchen
    master_urls = [
        url
        for url in urls
        if is_master_playlist(url)
    ]

    if master_urls:

        print("")
        print(
            "[NOW TV] Masterplaylist gefunden."
        )

        for url in master_urls:

            print(
                f"[NOW TV] Prüfe Master:\n{url}"
            )

            if validate_stream(
                url,
                request_context
            ):

                print("")
                print(
                    "[NOW TV] ✓ MASTER PLAYLIST GÜLTIG"
                )

                return url

    # Danach andere Streams
    for url in urls:

        if url in master_urls:
            continue

        print("")
        print(
            f"[NOW TV] Prüfe Stream:\n{url}"
        )

        if validate_stream(
            url,
            request_context
        ):

            print(
                "[NOW TV] ✓ Gültiger HLS Stream"
            )

            return url

    return None


# ============================================================
# FALLBACK
# ============================================================

FALLBACK_STREAMS = [

    # Bekannte NOW-TV Masterplaylist
    "https://nowtv-live-ad.ercdn.net/nowtv/playlist.m3u8",

    # Öffentliche TurkNet-Alternative
    "https://uycyyuuzyh.turknet.ercdn.net/nphindgytw/nowtv/nowtv.m3u8",
]


def fallback_find(request_context):

    print("")
    print("======================================")
    print("NOW TV FALLBACK")
    print("======================================")

    for url in FALLBACK_STREAMS:

        print("")
        print(
            f"[NOW TV] Fallback prüfe:\n{url}"
        )

        if validate_stream(
            url,
            request_context
        ):

            print("")
            print(
                f"[NOW TV] ✓ Fallback funktioniert:\n{url}"
            )

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

    # WICHTIG:
    # Dein Workflow erwartet diese Datei
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
        encoding="utf-8",
        newline="\n"
    ) as f:

        f.write(content)

    print("")
    print("======================================")
    print("NOW TV M3U8")
    print("======================================")
    print(content)


# ============================================================
# FEHLERDATEI
# ============================================================

def write_error(message):

    os.makedirs(
        "streams",
        exist_ok=True
    )

    with open(
        "streams/nowtv.error.txt",
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
                "--disable-blink-features=AutomationControlled",
            ],
        )

        request_context = (
            p.request.new_context(
                user_agent=USER_AGENT,
                ignore_https_errors=True,
            )
        )

        try:

            # Browser Scan
            urls = browser_find_stream(
                browser
            )

            print("")
            print(
                f"[NOW TV] "
                f"{len(urls)} M3U8 URLs gefunden."
            )

            # Beste URL bestimmen
            stream = pick_best_stream(
                urls,
                request_context,
            )

            # Fallback
            if not stream:

                stream = fallback_find(
                    request_context
                )

            # Erfolgreich
            if stream:

                write_nowtv(
                    stream
                )

                error_file = (
                    "streams/nowtv.error.txt"
                )

                if os.path.exists(
                    error_file
                ):
                    os.remove(
                        error_file
                    )

                print("")
                print(
                    "======================================"
                )
                print(
                    "✓ NOW TV erfolgreich"
                )
                print(
                    "======================================"
                )

            else:

                write_error(
                    "NOW TV Stream konnte nicht "
                    "gefunden oder validiert werden."
                )

                print("")
                print(
                    "✗ NOW TV Stream nicht gefunden."
                )

                # Alte funktionierende M3U8
                # NICHT löschen!

        finally:

            request_context.dispose()
            browser.close()


if __name__ == "__main__":
    main()
