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
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

STREAM_REGEX = re.compile(
    r'https?://[^\s"\'<>]+\.m3u8(?:\?[^\s"\'<>]*)?',
    re.IGNORECASE
)

RELATIVE_M3U8_REGEX = re.compile(
    r'["\']([^"\']+\.m3u8(?:\?[^"\']*)?)["\']',
    re.IGNORECASE
)


# ============================================================
# URL yardımcıları
# ============================================================

def normalize_url(url, base_url=None):
    if not url:
        return None

    url = url.strip().strip('"\'')
    url = url.replace("\\/", "/")

    if url.startswith("//"):
        url = "https:" + url

    if base_url and url.startswith("/"):
        parsed = urlparse(base_url)
        url = f"{parsed.scheme}://{parsed.netloc}{url}"

    elif base_url and not url.startswith(("http://", "https://")):
        base = base_url.rsplit("/", 1)[0] + "/"
        url = base + url

    return url


def decode_base64(value):
    try:
        value += "=" * (-len(value) % 4)
        return base64.b64decode(value).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def extract_m3u8(text, base_url=None):
    if not text:
        return []

    found = []

    # Absolute URLs
    for match in STREAM_REGEX.findall(text):
        url = normalize_url(match, base_url)
        if url:
            found.append(url)

    # Relative URLs
    for match in RELATIVE_M3U8_REGEX.findall(text):
        url = normalize_url(match, base_url)
        if url:
            found.append(url)

    # Base64 içinden gelebilecek URL
    for token in re.findall(r'["\']([A-Za-z0-9+/=_-]{40,})["\']', text):
        decoded = decode_base64(token)

        if ".m3u8" in decoded.lower():
            for match in STREAM_REGEX.findall(decoded):
                url = normalize_url(match, base_url)
                if url:
                    found.append(url)

    return list(dict.fromkeys(found))


# ============================================================
# HLS kontrolü
# ============================================================

def is_hls_response(response):
    try:
        content_type = (
            response.headers.get("content-type", "")
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
            timeout=12000,
            headers={
                "User-Agent": USER_AGENT,
                "Referer": REFERER,
                "Origin": "https://www.nowtv.com.tr",
                "Accept": (
                    "application/vnd.apple.mpegurl,"
                    "application/x-mpegURL,"
                    "application/octet-stream,"
                    "*/*"
                ),
            },
        )

        if response.status != 200:
            print(
                f"[NOW TV] HTTP {response.status}: {url}"
            )
            return False

        if is_hls_response(response):
            return True

    except Exception as e:
        print(
            f"[NOW TV] Stream kontrol hatası: {e}"
        )

    return False


# ============================================================
# Token
# ============================================================

def token_remaining_seconds(url):
    """
    NOW TV URL'lerinde:
        e=UNIX_TIMESTAMP

    şeklinde token expiration bulunabilir.
    """

    match = re.search(r"(?:[?&])e=(\d+)", url)

    if not match:
        return 999999999

    try:
        expires = int(match.group(1))
        return expires - int(time.time())
    except Exception:
        return 0


# ============================================================
# Sayfayı tara
# ============================================================

def scan_page(page):
    urls = []

    # --------------------------------------------------------
    # Performance entries
    # --------------------------------------------------------

    try:
        resources = page.evaluate(
            """
            () => performance.getEntriesByType('resource')
                .map(x => x.name)
            """
        )

        for resource in resources:
            urls.extend(
                extract_m3u8(resource, page.url)
            )

    except Exception:
        pass

    # --------------------------------------------------------
    # HTML
    # --------------------------------------------------------

    try:
        html = page.content()

        urls.extend(
            extract_m3u8(html, page.url)
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
                () => performance.getEntriesByType('resource')
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
# Browser ile NOW TV bul
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
            f"[NOW TV] Açılıyor: {CHANNEL['url']}"
        )

        page.goto(
            CHANNEL["url"],
            wait_until="domcontentloaded",
            timeout=30000,
        )

        # İlk network çağrılarının oluşmasını bekle
        page.wait_for_timeout(3000)

        discovered.extend(
            scan_page(page)
        )

        # Video elementlerini başlat
        try:
            page.evaluate(
                """
                () => {
                    document.querySelectorAll('video').forEach(v => {
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

        # Biraz daha bekle
        for _ in range(4):

            page.wait_for_timeout(2000)

            discovered.extend(
                scan_page(page)
            )

            if discovered:
                break

    except Exception as e:

        print(
            f"[NOW TV] Browser hatası: {e}"
        )

    finally:
        context.close()

    return list(dict.fromkeys(discovered))


# ============================================================
# En iyi stream'i seç
# ============================================================

def pick_best_stream(urls, request_context):

    if not urls:
        return None

    # Sadece NOW TV CDN streamlerini tercih et
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

    # Token süresi en uzun olanları önce dene
    urls = sorted(
        urls,
        key=token_remaining_seconds,
        reverse=True,
    )

    print("")
    print("[NOW TV] Bulunan streamler:")

    for url in urls:
        remaining = token_remaining_seconds(url)

        print(
            f"  {remaining}s -> {url}"
        )

    # Doğrula
    for url in urls:

        print("")
        print(
            f"[NOW TV] Kontrol ediliyor:\n{url}"
        )

        if validate_stream(
            url,
            request_context
        ):

            print(
                "[NOW TV] ✓ Geçerli HLS stream bulundu"
            )

            return url

    return None


# ============================================================
# Fallback
# ============================================================

FALLBACK_STREAMS = [
    "https://nowtv-live-ad.ercdn.net/nowtv/playlist.m3u8",
]


def fallback_find(request_context):

    print("")
    print("[NOW TV] Fallback deneniyor...")

    for url in FALLBACK_STREAMS:

        if validate_stream(
            url,
            request_context
        ):

            print(
                f"[NOW TV] ✓ Fallback çalışıyor:\n{url}"
            )

            return url

    return None


# ============================================================
# M3U oluştur
# ============================================================

def write_nowtv(stream_url):

    os.makedirs(
        "streams",
        exist_ok=True
    )

    path = "streams/nowtv.m3u"

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
    print("NOW TV M3U")
    print("======================================")
    print(content)


# ============================================================
# Error
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

        f.write(message + "\n")


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

        request_context = p.request.new_context(
            user_agent=USER_AGENT,
            ignore_https_errors=True,
        )

        try:

            # ----------------------------------------------
            # Browser scan
            # ----------------------------------------------

            urls = browser_find_stream(
                browser
            )

            print("")
            print(
                f"[NOW TV] {len(urls)} stream bulundu."
            )

            # ----------------------------------------------
            # Geçerli stream seç
            # ----------------------------------------------

            stream = pick_best_stream(
                urls,
                request_context,
            )

            # ----------------------------------------------
            # Fallback
            # ----------------------------------------------

            if not stream:

                stream = fallback_find(
                    request_context
                )

            # ----------------------------------------------
            # Sonuç
            # ----------------------------------------------

            if stream:

                write_nowtv(stream)

                # Eski error dosyasını kaldır
                error_file = (
                    "streams/nowtv.error.txt"
                )

                if os.path.exists(error_file):
                    os.remove(error_file)

                print("")
                print(
                    "✓ NOW TV başarıyla bulundu."
                )

            else:

                write_error(
                    "NOW TV stream bulunamadı."
                )

                print("")
                print(
                    "✗ NOW TV stream bulunamadı."
                )

                # Eski çalışan M3U'yu silme!
                # Böylece geçici bir hata nedeniyle
                # çalışan URL kaybolmaz.

        finally:

            request_context.dispose()
            browser.close()


if __name__ == "__main__":
    main()
