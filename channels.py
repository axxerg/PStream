import os
import re
import time
import base64
import threading
from urllib.parse import urljoin, urlparse, parse_qs

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


# ============================================================
# KONFIGURATION
# ============================================================

CHANNELS = {
    "showtv": {"name": "Show TV", "url": "https://www.showtv.com.tr/canli-yayin"},
    "showturk": {"name": "ShowTurk", "url": "https://www.showturk.com.tr/canli-yayin"},
    "showmax": {"name": "Showmax", "url": "https://www.showmax.com.tr/"},
    "nowtv": {"name": "NOW TV", "url": "https://www.nowtv.com.tr/canli-yayin"},
    "tv8": {"name": "TV8", "url": "https://www.tv8.com.tr/canli-yayin"},
    "tv8int": {"name": "TV8 International", "url": "https://www.tv8.com.tr/tv8-international"},
    "kanald": {"name": "Kanal D", "url": "https://www.kanald.com.tr/canli-yayin"},
    "eurod": {"name": "Euro D", "url": "https://www.eurod.com.tr/canli-yayin"},
    "teve2": {"name": "Teve2", "url": "https://www.teve2.com.tr/canli-yayin"},
    "startv": {"name": "Star TV", "url": "https://www.startv.com.tr/canli-yayin"},
    "eurostar": {"name": "Eurostar TV", "url": "https://www.eurostartv.com.tr/canli-izle"},
}


FALLBACK_STREAMS = {
    "showtv": [
        "https://ciner-live.ercdn.net/showtv/playlist.m3u8"
    ],

    "showturk": [
        "https://ciner-live.ercdn.net/showturk/playlist.m3u8"
    ],

    "showmax": [
        "https://ciner-live.ercdn.net/showmax/playlist.m3u8"
    ],

    "nowtv": [
        "https://ciner-live.ercdn.net/nowtv/playlist.m3u8"
    ],

    "tv8": [
        "https://tv8.daioncdn.net/tv8/tv8.m3u8",
        "https://tv8.daioncdn.net/tv8/tv8_720p.m3u8",
        "https://tv8.daioncdn.net/tv8/tv8_1080p.m3u8",
    ],

    "tv8int": [
        "https://tv8.daioncdn.net/tv8/tv8.m3u8",
        "https://tv8.daioncdn.net/tv8/tv8_720p.m3u8",
        "https://tv8.daioncdn.net/tv8/tv8_1080p.m3u8",
    ],

    "kanald": [
        "https://kanald-live.daioncdn.net/kanald/kanald.m3u8",
        "https://kanald-live.daioncdn.net/kanald/kanald_720p.m3u8",
    ],

    "eurod": [
        "https://eurod-live.daioncdn.net/eurod/eurod.m3u8",
        "https://eurod-live.daioncdn.net/eurod/eurod_720p.m3u8",
    ],

    "teve2": [
        "https://teve2-live.daioncdn.net/teve2/teve2.m3u8",
        "https://teve2-live.daioncdn.net/teve2/teve2_720p.m3u8",
    ],

    "startv": [
        "https://dogus-live.daioncdn.net/startv/startv.m3u8",
        "https://dogus-live.daioncdn.net/startv/startv_720p.m3u8",
        "https://trn03.tulix.tv/gt-startv/playlist.m3u8",
    ],

    "eurostar": [
        "https://tgn.bozztv.com/trn03/gt-eurostar/index.m3u8",
        "https://trn10.tulix.tv/gt-eurostar/index.m3u8",
    ],
}


REFERERS = {
    "showtv": "https://www.showtv.com.tr/",
    "showturk": "https://www.showturk.com.tr/",
    "showmax": "https://www.showmax.com.tr/",
    "nowtv": "https://www.nowtv.com.tr/",
    "tv8": "https://www.tv8.com.tr/",
    "tv8int": "https://www.tv8.com.tr/",
    "kanald": "https://www.kanald.com.tr/",
    "eurod": "https://www.eurod.com.tr/",
    "teve2": "https://www.teve2.com.tr/",
    "startv": "https://www.startv.com.tr/",
    "eurostar": "https://www.eurostartv.com.tr/",
}


# ============================================================
# DEINE HAUPTPLAYLIST
# ============================================================

PLAYLIST_FILE = os.path.join(
    "PStream",
    "2026",
    "playlist.m3u"
)


USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)


M3U8_REGEX = re.compile(
    r"""https?://[^\s"'<>\\]+?\.m3u8(?:\?[^\s"'<>\\]*)?""",
    re.IGNORECASE,
)


RELATIVE_M3U8_REGEX = re.compile(
    r"""["']([^"']+?\.m3u8(?:\?[^"']*)?)["']""",
    re.IGNORECASE,
)


_validate_cache = {}
_validate_lock = threading.Lock()


# ============================================================
# URL FUNKTIONEN
# ============================================================

def normalize_url(url, base_url=None):

    if not url:
        return None

    url = str(url).strip()

    url = (
        url
        .replace("\\/", "/")
        .replace("\\u002F", "/")
        .replace("&amp;", "&")
    )

    if url.startswith("//"):
        url = "https:" + url

    if base_url and not url.startswith(
        ("http://", "https://")
    ):
        url = urljoin(
            base_url,
            url
        )

    if not url.startswith(
        ("http://", "https://")
    ):
        return None

    return url


def decode_base64(value):

    try:

        value = value.strip()

        if len(value) < 20:
            return None

        value += "=" * (
            -len(value) % 4
        )

        decoded = base64.b64decode(
            value,
            validate=False
        ).decode(
            "utf-8",
            errors="ignore"
        )

        if ".m3u8" in decoded.lower():
            return decoded

    except Exception:
        pass

    return None


def extract_m3u8(text, base_url):

    found = []

    if not text:
        return found

    for match in M3U8_REGEX.findall(text):

        url = normalize_url(
            match,
            base_url
        )

        if url and url not in found:
            found.append(url)

    for match in RELATIVE_M3U8_REGEX.findall(text):

        url = normalize_url(
            match,
            base_url
        )

        if url and url not in found:
            found.append(url)

    cleaned = (
        text
        .replace("\\/", "/")
        .replace("\\u002F", "/")
        .replace("&amp;", "&")
    )

    for match in M3U8_REGEX.findall(cleaned):

        url = normalize_url(
            match,
            base_url
        )

        if url and url not in found:
            found.append(url)

    tokens = re.findall(
        r"[A-Za-z0-9+/=_-]{40,}",
        text
    )

    for token in tokens[:100]:

        decoded = decode_base64(token)

        if not decoded:
            continue

        for match in M3U8_REGEX.findall(decoded):

            url = normalize_url(
                match,
                base_url
            )

            if url and url not in found:
                found.append(url)

    return found


def unique_urls(urls):

    result = []
    seen = set()

    for url in urls:

        if not url:
            continue

        url = url.strip()

        if url in seen:
            continue

        seen.add(url)
        result.append(url)

    return result


def token_expired(url):

    try:

        query = parse_qs(
            urlparse(url).query
        )

        if "e" not in query:
            return False

        expires = int(
            query["e"][0]
        )

        if expires > 10 ** 12:
            expires //= 1000

        return expires <= (
            int(time.time()) + 30
        )

    except Exception:
        return False


def token_remaining_seconds(url):

    try:

        query = parse_qs(
            urlparse(url).query
        )

        if "e" not in query:
            return None

        expires = int(
            query["e"][0]
        )

        if expires > 10 ** 12:
            expires //= 1000

        return expires - int(
            time.time()
        )

    except Exception:
        return None


# ============================================================
# PLAYLIST ERKENNEN
# ============================================================

def is_master_playlist(url):

    u = url.lower()

    if re.search(
        r"[/_-]\d{3,4}p\.m3u8",
        u
    ):
        return False

    if re.search(
        r"_hd\.m3u8",
        u
    ):
        return False

    if re.search(
        r"_sd\.m3u8",
        u
    ):
        return False

    if re.search(
        r"_\d{3,4}\.m3u8",
        u
    ):
        return False

    if re.search(
        r"[/_-]playlist\.m3u8",
        u
    ):
        return True

    if re.search(
        r"[/_-]master\.m3u8",
        u
    ):
        return True

    if re.search(
        r"[/_-]index\.m3u8",
        u
    ):
        return True

    return False


def quality_from_url(url):

    u = url.lower()

    m = re.search(
        r"[/_-](\d{3,4})p\.m3u8",
        u
    )

    if m:
        return int(m.group(1))

    if "_hd" in u:
        return 720

    if "_sd" in u:
        return 480

    if "1080" in u:
        return 1080

    if "720" in u:
        return 720

    if "576" in u:
        return 576

    if "480" in u:
        return 480

    if "360" in u:
        return 360

    return 0


def score_stream(url):

    u = url.lower()

    score = 0

    if ".m3u8" in u:
        score += 50

    if is_master_playlist(url):
        score += 200

    score += (
        quality_from_url(url) // 10
    )

    if (
        re.search(r"[/_-]live", u)
        or "/live/" in u
    ):
        score += 10

    if re.search(
        r"[/_-]stream",
        u
    ):
        score += 10

    if "?st=" in u or "&st=" in u:
        score += 15

    if "&e=" in u or "?e=" in u:
        score += 10

    if "ercdn.net" in u:
        score += 20

    if "daioncdn.net" in u:
        score += 20

    remaining = token_remaining_seconds(url)

    if (
        remaining is not None
        and remaining > 60
    ):
        score += 30

    return score


# ============================================================
# STREAM VALIDIERUNG
# ============================================================

def validate_stream(
    url,
    page=None,
    use_cache=True,
    referer=None
):

    if not url:
        return False

    cache_key = url

    if use_cache:

        with _validate_lock:

            if cache_key in _validate_cache:
                return _validate_cache[
                    cache_key
                ]

    if token_expired(url):

        print(
            f"      [EXPIRED] {url}"
        )

        if use_cache:

            with _validate_lock:
                _validate_cache[
                    cache_key
                ] = False

        return False

    print("")
    print(
        f"      [TEST] {url}"
    )

    if not page:

        if use_cache:

            with _validate_lock:
                _validate_cache[
                    cache_key
                ] = False

        return False

    result = False

    try:

        headers = {
            "Accept": (
                "application/vnd.apple.mpegurl,"
                "application/x-mpegURL,"
                "application/octet-stream,*/*"
            )
        }

        if referer:

            headers["Referer"] = referer
            headers["Origin"] = (
                referer.rstrip("/")
            )

        response = page.request.get(
            url,
            timeout=20000,
            fail_on_status_code=False,
            headers=headers
        )

        status = response.status

        print(
            f"      [HTTP] {status}"
        )

        if status >= 400:

            print(
                f"      [X] HTTP {status}"
            )

        else:

            try:
                body = response.text()
            except Exception as e:
                print(
                    f"      [TEXT ERROR] "
                    f"{str(e)[:200]}"
                )
                body = ""

            body = body[:50000]

            if "#EXTM3U" in body:

                print(
                    "      [OK] "
                    "#EXTM3U tapildi"
                )

                result = True

            elif "#EXT-X-" in body:

                print(
                    "      [OK] "
                    "HLS playlist tapildi"
                )

                result = True

            else:

                try:

                    content_type = (
                        response.headers
                        .get(
                            "content-type",
                            ""
                        )
                        .lower()
                    )

                except Exception:

                    content_type = ""

                if (
                    "mpegurl" in content_type
                    or "vnd.apple.mpegurl"
                    in content_type
                ):

                    print(
                        "      [OK] "
                        "HLS content-type"
                    )

                    result = True

                else:

                    print(
                        "      [X] "
                        "HLS playlist "
                        "tesdiqlenmedi"
                    )

    except Exception as e:

        print(
            f"      [ERR] "
            f"{str(e)[:250]}"
        )

    if use_cache:

        with _validate_lock:
            _validate_cache[
                cache_key
            ] = result

    return result


# ============================================================
# MASTER PLAYLIST PARSEN
# ============================================================

def parse_master_playlist(
    body,
    base_url
):

    if (
        not body
        or "#EXTM3U" not in body
    ):
        return []

    if "#EXT-X-STREAM-INF" not in body:
        return []

    variants = []

    lines = body.splitlines()

    for i, line in enumerate(lines):

        line = line.strip()

        if not line.startswith(
            "#EXT-X-STREAM-INF"
        ):
            continue

        info = line.upper()

        bandwidth = 0
        resolution = None
        resolution_score = 0

        bw_match = re.search(
            r"BANDWIDTH=(\d+)",
            info
        )

        if bw_match:
            bandwidth = int(
                bw_match.group(1)
            )

        res_match = re.search(
            r"RESOLUTION=(\d+)X(\d+)",
            info
        )

        if res_match:

            width = int(
                res_match.group(1)
            )

            height = int(
                res_match.group(2)
            )

            resolution = (
                f"{width}x{height}"
            )

            resolution_score = (
                width * height
            )

        for next_line in lines[
            i + 1:
        ]:

            next_line = (
                next_line.strip()
            )

            if (
                not next_line
                or next_line.startswith("#")
            ):
                continue

            variant_url = normalize_url(
                next_line,
                base_url
            )

            if variant_url:

                variants.append({
                    "url": variant_url,
                    "bandwidth": bandwidth,
                    "resolution": resolution,
                    "resolution_score":
                        resolution_score,
                    "quality": (
                        quality_from_url(
                            variant_url
                        )
                        or (
                            resolution_score // 1000
                            if resolution_score
                            else 0
                        )
                    ),
                })

            break

    return variants


def fetch_master_playlist(
    url,
    page,
    referer=None
):

    if not url:
        return None

    if token_expired(url):

        print(
            "      [MASTER] "
            "Token vaxti bitib"
        )

        return None

    try:

        headers = {
            "Accept": (
                "application/vnd.apple.mpegurl,"
                "application/x-mpegURL,"
                "application/octet-stream,*/*"
            )
        }

        if referer:

            headers["Referer"] = referer
            headers["Origin"] = (
                referer.rstrip("/")
            )

        response = page.request.get(
            url,
            timeout=20000,
            fail_on_status_code=False,
            headers=headers
        )

        if response.status >= 400:
            return None

        body = response.text()

        if "#EXTM3U" not in body:
            return None

        return body

    except Exception as e:

        print(
            f"      [MASTER ERROR] "
            f"{str(e)[:200]}"
        )

        return None


def collect_all_variants(
    master_url,
    page,
    referer=None
):

    print("")
    print(
        f"      [MASTER] "
        f"{master_url}"
    )

    body = fetch_master_playlist(
        master_url,
        page,
        referer=referer
    )

    if not body:

        print(
            "      [MASTER] Alinmadi"
        )

        return []

    variants = parse_master_playlist(
        body,
        master_url
    )

    if not variants:

        print(
            "      [MASTER] "
            "Variant yoxdur "
            "(media playlist)"
        )

        return []

    print(
        f"      [MASTER] "
        f"{len(variants)} variant tapildi"
    )

    valid = []

    for v in variants:

        if token_expired(
            v["url"]
        ):

            print(
                f"      [VARIANT] "
                f"[EXPIRED] "
                f"{v['url']}"
            )

            continue

        print(
            f"      [VARIANT] "
            f"{v['resolution'] or v['quality']}p - "
            f"{v['url']}"
        )

        if validate_stream(
            v["url"],
            page,
            referer=referer
        ):

            v["valid"] = True
            valid.append(v)

            print(
                f"      [VARIANT] "
                f"[OK] "
                f"{v['resolution'] or v['quality']}p"
            )

        else:

            print(
                f"      [VARIANT] "
                f"[X] "
                f"{v['resolution'] or v['quality']}p"
            )

    valid.sort(
        key=lambda x: (
            x["resolution_score"],
            x["bandwidth"]
        ),
        reverse=True
    )

    return valid


# ============================================================
# SEITE SCANNEN
# ============================================================

def scan_page(
    page,
    page_url
):

    found = []

    def add(
        url,
        source
    ):

        url = normalize_url(
            url,
            page_url
        )

        if not url:
            return

        if ".m3u8" not in url.lower():
            return

        if url not in found:

            found.append(url)

            print(
                f"      [M3U8] "
                f"{source}: "
                f"{url}"
            )

    try:

        performance_urls = page.evaluate(
            "() => performance.getEntriesByType('resource').map(x => x.name)"
        )

        for url in performance_urls:

            if ".m3u8" in url.lower():
                add(
                    url,
                    "PERFORMANCE"
                )

    except Exception as e:

        print(
            f"      [PERFORMANCE ERROR] "
            f"{str(e)[:150]}"
        )

    try:

        html = page.content()

        for url in extract_m3u8(
            html,
            page_url
        ):

            add(
                url,
                "HTML"
            )

    except Exception as e:

        print(
            f"      [HTML ERROR] "
            f"{str(e)[:150]}"
        )

    try:

        frames = page.frames

        print(
            f"      [INFO] "
            f"Frame sayi: "
            f"{len(frames)}"
        )

        for frame in frames:

            try:

                frame_url = frame.url

                if (
                    not frame_url
                    or frame_url == "about:blank"
                ):
                    continue

                print(
                    f"      [FRAME] "
                    f"{frame_url}"
                )

                frame_html = frame.content()

                for url in extract_m3u8(
                    frame_html,
                    frame_url
                ):

                    add(
                        url,
                        "IFRAME"
                    )

                try:

                    entries = frame.evaluate(
                        "() => performance.getEntriesByType('resource').map(x => x.name)"
                    )

                    for url in entries:

                        if ".m3u8" in url.lower():

                            add(
                                url,
                                "FRAME-PERFORMANCE"
                            )

                except Exception as e:

                    print(
                        f"      [FRAME-EVAL ERROR] "
                        f"{str(e)[:120]}"
                    )

            except Exception as e:

                print(
                    f"      [FRAME SKIP] "
                    f"{str(e)[:120]}"
                )

    except Exception as e:

        print(
            f"      [FRAME ERROR] "
            f"{str(e)[:150]}"
        )

    return unique_urls(found)


# ============================================================
# BESTEN STREAM AUSWÄHLEN
# ============================================================

def pick_best_master(
    candidates,
    page,
    referer=None
):

    if not candidates:
        return None

    masters = [
        u for u in candidates
        if is_master_playlist(u)
    ]

    others = [
        u for u in candidates
        if not is_master_playlist(u)
    ]

    def sort_key(u):

        rem = token_remaining_seconds(u)

        if rem is None:
            return (0, 0)

        return (
            1,
            rem
        )

    masters.sort(
        key=sort_key,
        reverse=True
    )

    others.sort(
        key=sort_key,
        reverse=True
    )

    for candidate in (
        masters + others
    ):

        print("")
        print(
            f"      [CHECK] "
            f"{candidate}"
        )

        if validate_stream(
            candidate,
            page,
            referer=referer
        ):

            print("")
            print(
                "      [SUCCESS]"
            )

            print(
                f"      {candidate}"
            )

            return candidate

    return None


# ============================================================
# BROWSER STREAM FINDER
# ============================================================

def browser_find_stream(
    page,
    channel_id,
    channel
):

    name = channel["name"]
    page_url = channel["url"]

    referer = REFERERS.get(
        channel_id,
        page_url
    )

    print("")
    print("=" * 70)
    print(
        f"[BROWSER] {name}"
    )
    print(
        f"[URL] {page_url}"
    )
    print("=" * 70)

    candidates = []
    network_urls = []

    def capture_response(
        response
    ):

        try:

            url = response.url

            if (
                ".m3u8" in url.lower()
                and url not in network_urls
            ):

                network_urls.append(
                    url
                )

                print(
                    f"      [NETWORK] "
                    f"{url}"
                )

        except Exception:
            pass

    page.on(
        "response",
        capture_response
    )

    try:

        print(
            "      [OPEN] "
            "Sayt acilir..."
        )

        page.goto(
            page_url,
            wait_until="domcontentloaded",
            timeout=40000
        )

        try:

            print(
                f"      [TITLE] "
                f"{page.title()}"
            )

        except Exception:
            pass

    except PlaywrightTimeoutError:

        print(
            "      [WARN] "
            "Sayt timeout oldu."
        )

    except Exception as e:

        print(
            f"      [OPEN ERROR] "
            f"{str(e)[:250]}"
        )

    print(
        "      [WAIT] "
        "Player gozlenilir..."
    )

    for i in range(10):

        try:
            page.wait_for_timeout(
                4000
            )
        except Exception:
            pass

        print(
            f"      [WAIT] "
            f"{(i + 1) * 4} saniye..."
        )

    try:

        page.evaluate(
            """
            () => {
                document.querySelectorAll('video').forEach(v => {
                    try {
                        v.muted = true;
                        v.autoplay = true;
                        const p = v.play();
                        if (p) p.catch(() => {});
                    } catch(e) {}
                });
            }
            """
        )

        page.wait_for_timeout(
            4000
        )

    except Exception:
        pass

    candidates.extend(
        network_urls
    )

    try:

        candidates.extend(
            scan_page(
                page,
                page_url
            )
        )

    except Exception as e:

        print(
            f"      [SCAN ERROR] "
            f"{str(e)[:200]}"
        )

    try:

        entries = page.evaluate(
            "() => performance.getEntriesByType('resource').map(x => x.name)"
        )

        for url in entries:

            if ".m3u8" in url.lower():
                candidates.append(url)

    except Exception:
        pass

    candidates = unique_urls(
        candidates
    )

    candidates = [
        x for x in candidates
        if not token_expired(x)
    ]

    candidates.sort(
        key=score_stream,
        reverse=True
    )

    print("")
    print(
        f"      [FOUND] "
        f"{len(candidates)} aktual URL"
    )

    best_master = pick_best_master(
        candidates,
        page,
        referer=referer
    )

    try:

        page.remove_listener(
            "response",
            capture_response
        )

    except Exception:
        pass

    if not best_master:
        return None, []

    variants = collect_all_variants(
        best_master,
        page,
        referer=referer
    )

    if not variants:
        return (
            best_master,
            []
        )

    return (
        best_master,
        variants
    )


# ============================================================
# FALLBACK
# ============================================================

def fallback_find(
    request_context,
    channel_id
):

    urls = FALLBACK_STREAMS.get(
        channel_id,
        []
    )

    if not urls:
        return None, []

    print("")
    print(
        f"[FALLBACK] "
        f"{channel_id}"
    )
    print("-" * 70)

    def sort_key(u):

        rem = token_remaining_seconds(u)

        if rem is None:
            return (0, 0)

        return (
            1,
            rem
        )

    sorted_urls = sorted(
        urls,
        key=sort_key,
        reverse=True
    )

    for url in sorted_urls:

        if token_expired(url):

            print(
                f"   [EXPIRED] "
                f"{url}"
            )

            continue

        print(
            f"   [TRY] "
            f"{url}"
        )

        try:

            response = request_context.get(
                url,
                timeout=20000,
                fail_on_status_code=False
            )

            print(
                f"   [STATUS] "
                f"{response.status}"
            )

            if response.status >= 400:
                continue

            try:
                body = response.text()
            except Exception:
                body = ""

            if (
                "#EXTM3U" in body
                or "#EXT-X-" in body
            ):

                print(
                    "   [OK] "
                    "Fallback isleyir"
                )

                variants = (
                    parse_master_playlist(
                        body,
                        url
                    )
                )

                valid = []

                for v in variants:

                    try:

                        r = request_context.get(
                            v["url"],
                            timeout=15000,
                            fail_on_status_code=False
                        )

                        if r.status < 400:

                            v["valid"] = True
                            valid.append(v)

                    except Exception:
                        pass

                if valid:

                    valid.sort(
                        key=lambda x: (
                            x["resolution_score"],
                            x["bandwidth"]
                        ),
                        reverse=True
                    )

                return (
                    url,
                    valid
                )

            try:

                content_type = (
                    response.headers
                    .get(
                        "content-type",
                        ""
                    )
                    .lower()
                )

            except Exception:

                content_type = ""

            if (
                "mpegurl" in content_type
                or "vnd.apple.mpegurl"
                in content_type
            ):

                print(
                    "   [OK] "
                    "HLS Content-Type"
                )

                return (
                    url,
                    []
                )

        except Exception as e:

            print(
                f"   [ERROR] "
                f"{str(e)[:200]}"
            )

    return None, []


# ============================================================
# STREAMS ORDNER
# ============================================================

def prepare_folders():

    os.makedirs(
        "streams",
        exist_ok=True
    )

    for f in os.listdir(
        "streams"
    ):

        if (
            f.endswith(".m3u")
            or f.endswith(".m3u8")
            or f.endswith(".error.txt")
            or f in (
                "links.txt",
                "github_links.txt"
            )
        ):

            try:

                os.remove(
                    os.path.join(
                        "streams",
                        f
                    )
                )

            except Exception:
                pass

    print(
        "[CLEAN] "
        "streams/ kohne fayllar silindi"
    )


def write_m3u(
    channel_id,
    channel,
    stream_url
):

    path = os.path.join(
        "streams",
        f"{channel_id}.m3u"
    )

    content = (
        "#EXTM3U\n"
        f'#EXTINF:-1 '
        f'tvg-id="{channel_id}" '
        f'tvg-name="{channel["name"]}" '
        f'group-title="Turkiye",'
        f'{channel["name"]}\n'
        f"{stream_url}\n"
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            content
        )

    print(
        f"[WRITE] "
        f"{path}"
    )


def build_quality_playlist(
    channel_id,
    channel,
    variants
):

    lines = [
        "#EXTM3U",
        "#EXT-X-VERSION:3"
    ]

    for v in variants:

        bw = (
            v.get("bandwidth")
            or 0
        )

        res = (
            v.get("resolution")
            or ""
        )

        if not res:

            q = (
                v.get("quality")
                or 0
            )

            if q >= 720:
                res = "1280x720"

            elif q >= 576:
                res = "1024x576"

            elif q >= 480:
                res = "854x480"

            elif q >= 360:
                res = "640x360"

            else:
                res = "640x360"

        if bw <= 0:
            bw = 1000000

        lines.append(
            f"#EXT-X-STREAM-INF:"
            f"PROGRAM-ID=1,"
            f"BANDWIDTH={bw},"
            f"CODECS=\"\","
            f"RESOLUTION={res}"
        )

        lines.append(
            v["url"]
        )

    return (
        "\n".join(lines)
        + "\n"
    )


def write_quality_playlist(
    channel_id,
    channel,
    variants
):

    if not variants:
        return None

    path = os.path.join(
        "streams",
        f"{channel_id}_all.m3u8"
    )

    content = (
        build_quality_playlist(
            channel_id,
            channel,
            variants
        )
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            content
        )

    print(
        f"[WRITE] "
        f"{path}"
    )

    return path


def write_error(
    channel_id,
    channel
):

    path = os.path.join(
        "streams",
        f"{channel_id}.error.txt"
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            f"Kanal: {channel['name']}\n"
            f"URL: {channel['url']}\n"
            f"Status: M3U8 tapilmadi\n"
            f"Vaxt: "
            f"{time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n"
        )

    print(
        f"[ERROR FILE] "
        f"{path}"
    )


# ============================================================
# HAUPTPLAYLIST ERKENNEN
# ============================================================

def playlist_channel_matches(
    line,
    cid
):

    if not line.startswith(
        "#EXTINF"
    ):
        return False

    text = line.lower()

    if cid == "showtv":

        return (
            "show.tv..tr" in text
            or "show tv" in text
            or "showtv" in text
        )

    if cid == "showturk":

        return (
            "show türk" in text
            or "showturk" in text
        )

    if cid == "nowtv":

        return (
            'tvg-id="fox.tr"' in text
            or ",now" in text
            or ", now" in text
        )

    if cid == "tv8":

        return (
            'tvg-id="tv8.hd.tr"' in text
            or 'tvg-id="tv8.tr"' in text
            or ",tv8" in text
            or ", tv8" in text
        )

    if cid == "tv8int":

        return (
            "tv8int" in text
            or "tv8 international" in text
        )

    if cid == "kanald":

        return (
            "kanal.d..tr" in text
            or "kanal d" in text
        )

    if cid == "eurod":

        return (
            "eurod.tr" in text
            or "euro d" in text
        )

    if cid == "teve2":

        return (
            "teve2" in text
            or "te ve2" in text
        )

    if cid == "startv":

        return (
            "star.tv..tr" in text
            or ",star" in text
            or ", star" in text
        )

    if cid == "eurostar":

        return (
            "eurostar.tr" in text
            or "euro star" in text
        )

    return False


def is_active_stream_line(
    line
):

    stripped = line.strip()

    if not stripped:
        return False

    if stripped.startswith("#"):
        return False

    return (
        stripped.startswith("http://")
        or stripped.startswith("https://")
    )


# ============================================================
# PStream/2026/playlist.m3u AKTUALISIEREN
# ============================================================

def update_existing_playlist(
    results
):

    print("")
    print("=" * 70)
    print(
        "[PLAYLIST] "
        "Hauptplaylist wird aktualisiert"
    )
    print(
        f"[FILE] "
        f"{PLAYLIST_FILE}"
    )
    print("=" * 70)

    if not os.path.exists(
        PLAYLIST_FILE
    ):

        print(
            f"[PLAYLIST ERROR] "
            f"Datei nicht gefunden: "
            f"{PLAYLIST_FILE}"
        )

        return False

    try:

        with open(
            PLAYLIST_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            lines = f.readlines()

    except Exception as e:

        print(
            f"[PLAYLIST ERROR] "
            f"Lesen fehlgeschlagen: "
            f"{e}"
        )

        return False

    updated = set()

    for cid, data in results.items():

        if not data:
            continue

        new_url = data.get(
            "master"
        )

        if not new_url:

            print(
                f"[PLAYLIST] "
                f"{CHANNELS[cid]['name']}: "
                f"kein neuer Stream"
            )

            continue

        found_entry = False

        for i, line in enumerate(
            lines
        ):

            if not playlist_channel_matches(
                line,
                cid
            ):
                continue

            found_entry = True

            # Nur innerhalb dieses EXTINF-Eintrags suchen
            for j in range(
                i + 1,
                min(
                    i + 15,
                    len(lines)
                )
            ):

                candidate = (
                    lines[j].strip()
                )

                # Nächster Sender
                if candidate.startswith(
                    "#EXTINF"
                ):
                    break

                # Leerzeile
                if not candidate:
                    continue

                # Kommentare / Backups
                if candidate.startswith("#"):
                    continue

                # Aktive URL
                if is_active_stream_line(
                    lines[j]
                ):

                    old_url = (
                        lines[j].strip()
                    )

                    if old_url != new_url:

                        lines[j] = (
                            new_url + "\n"
                        )

                        print("")
                        print(
                            f"[UPDATE] "
                            f"{CHANNELS[cid]['name']}"
                        )

                        print(
                            f"   OLD: "
                            f"{old_url}"
                        )

                        print(
                            f"   NEW: "
                            f"{new_url}"
                        )

                    else:

                        print(
                            f"[UNCHANGED] "
                            f"{CHANNELS[cid]['name']}"
                        )

                    updated.add(cid)

                    break

            if cid in updated:
                break

        if not found_entry:

            print(
                f"[PLAYLIST] "
                f"{CHANNELS[cid]['name']}: "
                f"#EXTINF nicht gefunden"
            )

    try:

        with open(
            PLAYLIST_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            f.writelines(
                lines
            )

    except Exception as e:

        print(
            f"[PLAYLIST ERROR] "
            f"Schreiben fehlgeschlagen: "
            f"{e}"
        )

        return False

    print("")
    print(
        f"[PLAYLIST] "
        f"{len(updated)} Sender "
        f"aktualisiert."
    )

    return True


# ============================================================
# ALLE STREAM-DATEIEN SCHREIBEN
# ============================================================

def write_all_m3u(
    results
):

    for cid, ch in CHANNELS.items():

        data = results.get(
            cid
        )

        if not data:
            continue

        master = data.get(
            "master"
        )

        variants = (
            data.get("variants")
            or []
        )

        if master:

            write_m3u(
                cid,
                ch,
                master
            )

        if variants:

            write_quality_playlist(
                cid,
                ch,
                variants
            )

    # streams/all.m3u

    all_path = os.path.join(
        "streams",
        "all.m3u"
    )

    lines = [
        "#EXTM3U"
    ]

    for cid, ch in CHANNELS.items():

        data = results.get(
            cid
        )

        if not data:
            continue

        master = data.get(
            "master"
        )

        if not master:
            continue

        lines.append(
            f'#EXTINF:-1 '
            f'tvg-id="{cid}" '
            f'tvg-name="{ch["name"]}" '
            f'group-title="Turkiye",'
            f'{ch["name"]}'
        )

        lines.append(
            master
        )

    with open(
        all_path,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            "\n".join(lines)
            + "\n"
        )

    print(
        f"[WRITE] "
        f"{all_path}"
    )

    # streams/links.txt

    links_path = os.path.join(
        "streams",
        "links.txt"
    )

    with open(
        links_path,
        "w",
        encoding="utf-8"
    ) as f:

        for cid, ch in CHANNELS.items():

            data = results.get(
                cid
            )

            if not data:
                continue

            master = data.get(
                "master"
            )

            if not master:
                continue

            f.write(
                f"# {ch['name']}\n"
                f"{master}\n\n"
            )

    print(
        f"[WRITE] "
        f"{links_path}"
    )

    # streams/github_links.txt

    repo = os.environ.get(
        "GITHUB_REPOSITORY",
        "USERNAME/REPO"
    )

    base = (
        "https://raw.githubusercontent.com/"
        f"{repo}/main/streams"
    )

    github_links_path = os.path.join(
        "streams",
        "github_links.txt"
    )

    with open(
        github_links_path,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            "# BUTUN KANALLAR (TEK playlist)\n"
        )

        f.write(
            f"{base}/all.m3u\n\n"
        )

        f.write(
            "# AYRI-AYRI KANALLAR\n"
        )

        for cid, ch in CHANNELS.items():

            data = results.get(
                cid
            )

            if not data:
                continue

            master = data.get(
                "master"
            )

            if not master:
                continue

            f.write(
                f"# {ch['name']}\n"
                f"{base}/{cid}.m3u\n"
            )

            if data.get(
                "variants"
            ):

                f.write(
                    f"# {ch['name']} - "
                    f"BUTUN KEYFIYYETLER\n"
                    f"{base}/{cid}_all.m3u8\n\n"
                )

            else:

                f.write(
                    "\n"
                )

    print(
        f"[WRITE] "
        f"{github_links_path}"
    )

    # ========================================================
    # DEINE GROSSE PLAYLIST AKTUALISIEREN
    # ========================================================

    update_existing_playlist(
        results
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("")
    print("=" * 70)
    print(
        "TURK TV LIVE M3U AUTO SCANNER"
    )
    print(
        "Playwright + Chromium + "
        "Full Quality Variants"
    )
    print(
        "PStream/2026/playlist.m3u UPDATE"
    )
    print("=" * 70)
    print("")

    print(
        "[STEP 1] "
        "Kohne fayllar silinir..."
    )

    prepare_folders()

    _validate_cache.clear()

    success = 0
    failed = 0

    results = {}

    print("")
    print(
        "[STEP 2] "
        "Kanallar scan edilir..."
    )

    with sync_playwright() as p:

        browser = p.chromium.launch(

            headless=True,

            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-software-rasterizer",
                "--autoplay-policy=no-user-gesture-required",
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
        )

        context = browser.new_context(

            ignore_https_errors=True,

            user_agent=USER_AGENT,

            viewport={
                "width": 1920,
                "height": 1080
            },

            locale="tr-TR",

            timezone_id="Europe/Istanbul",

            extra_http_headers={

                "Accept-Language":
                    "tr-TR,tr;q=0.9,en;q=0.8",

                "Accept":
                    "text/html,"
                    "application/xhtml+xml,"
                    "application/xml;q=0.9,"
                    "image/webp,*/*;q=0.8",
            },
        )

        context.add_init_script(
            "Object.defineProperty("
            "navigator, 'webdriver', "
            "{get: () => undefined}"
            ");"
        )

        request_context = (
            p.request.new_context(

                ignore_https_errors=True,

                extra_http_headers={

                    "User-Agent":
                        USER_AGENT,

                    "Accept":
                        "application/vnd.apple.mpegurl,"
                        "application/x-mpegURL,"
                        "application/octet-stream,*/*",

                    "Accept-Language":
                        "tr-TR,tr;q=0.9,en;q=0.8",
                },
            )
        )

        try:

            for cid, ch in CHANNELS.items():

                referer = REFERERS.get(
                    cid,
                    ch["url"]
                )

                page = (
                    context.new_page()
                )

                master = None
                variants = []

                try:

                    (
                        master,
                        variants
                    ) = browser_find_stream(
                        page,
                        cid,
                        ch
                    )

                except Exception as e:

                    print(
                        f"[BROWSER CRASH] "
                        f"{ch['name']}: "
                        f"{str(e)[:200]}"
                    )

                    master = None
                    variants = []

                finally:

                    try:
                        page.close()
                    except Exception:
                        pass

                # FALLBACK

                if not master:

                    print("")
                    print(
                        f"[BROWSER X] "
                        f"{ch['name']} "
                        f"tapilmadi"
                    )

                    try:

                        request_context.dispose()

                    except Exception:
                        pass

                    request_context = (
                        p.request.new_context(

                            ignore_https_errors=True,

                            extra_http_headers={

                                "User-Agent":
                                    USER_AGENT,

                                "Accept":
                                    "application/vnd.apple.mpegurl,"
                                    "application/x-mpegURL,"
                                    "application/octet-stream,*/*",

                                "Accept-Language":
                                    "tr-TR,tr;q=0.9,en;q=0.8",

                                "Referer":
                                    referer,

                                "Origin":
                                    referer.rstrip("/"),
                            },
                        )
                    )

                    try:

                        (
                            master,
                            variants
                        ) = fallback_find(
                            request_context,
                            cid
                        )

                    except Exception as e:

                        print(
                            f"[FALLBACK CRASH] "
                            f"{ch['name']}: "
                            f"{str(e)[:200]}"
                        )

                        master = None
                        variants = []

                results[cid] = {

                    "master":
                        master,

                    "variants":
                        variants,
                }

        finally:

            try:
                request_context.dispose()
            except Exception:
                pass

            try:
                context.close()
            except Exception:
                pass

            try:
                browser.close()
            except Exception:
                pass

    print("")
    print(
        "[STEP 3] "
        "Neticeler yazilir..."
    )

    write_all_m3u(
        results
    )

    # Ergebnis

    for cid, ch in CHANNELS.items():

        data = results.get(
            cid
        )

        master = (
            data.get("master")
            if data
            else None
        )

        variants = (
            data.get("variants")
            if data
            else []
        )

        if master:

            success += 1

            print(
                f"[OK] "
                f"{ch['name']} "
                f"({len(variants)} keyfiyyet)"
            )

        else:

            write_error(
                cid,
                ch
            )

            failed += 1

            print(
                f"[FAILED] "
                f"{ch['name']}"
            )

        print("")

    print("")
    print("=" * 70)
    print("NETICE")
    print("=" * 70)

    print(
        f"[OK] Ugurlu: "
        f"{success}"
    )

    print(
        f"[X] Tapilmadi: "
        f"{failed}"
    )

    print(
        f"[TOTAL] "
        f"{len(CHANNELS)}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()
