import os
import re
import time
import base64
from urllib.parse import urljoin, urlparse, parse_qs

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


# ============================================================
# KONFIGURATION
# ============================================================

CHANNELS = {
    "showtv": {
        "name": "Show TV",
        "url": "https://www.showtv.com.tr/canli-yayin"
    },

    "showturk": {
        "name": "ShowTurk",
        "url": "https://www.showturk.com.tr/canli-yayin"
    },

    "showmax": {
        "name": "Showmax",
        "url": "https://www.showmax.com.tr/"
    },

    "nowtv": {
        "name": "NOW TV",
        "url": "https://www.nowtv.com.tr/canli-yayin"
    },

    "atv": {
        "name": "ATV",
        "url": "https://www.atv.com.tr/canli-yayin"
    },

    "tv8": {
        "name": "TV8",
        "url": "https://www.tv8.com.tr/canli-yayin"
    },

    "tv8int": {
        "name": "TV8 International",
        "url": "https://www.tv8.com.tr/tv8-international"
    },

    "kanald": {
        "name": "Kanal D",
        "url": "https://www.kanald.com.tr/canli-yayin"
    },

    "eurod": {
        "name": "Euro D",
        "url": "https://www.eurod.com.tr/canli-yayin"
    },

    "teve2": {
        "name": "Teve2",
        "url": "https://www.teve2.com.tr/canli-yayin"
    },

    "startv": {
        "name": "Star TV",
        "url": "https://www.startv.com.tr/canli-yayin"
    },

    "eurostar": {
        "name": "Eurostar TV",
        "url": "https://www.eurostartv.com.tr/canli-izle"
    },
}


# ============================================================
# FALLBACK STREAMS
# ============================================================

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


# ============================================================
# REFERER
# ============================================================

REFERERS = {

    "showtv":
        "https://www.showtv.com.tr/",

    "showturk":
        "https://www.showturk.com.tr/",

    "showmax":
        "https://www.showmax.com.tr/",

    "nowtv":
        "https://www.nowtv.com.tr/",

    "atv":
        "https://www.atv.com.tr/",

    "tv8":
        "https://www.tv8.com.tr/",

    "tv8int":
        "https://www.tv8.com.tr/",

    "kanald":
        "https://www.kanald.com.tr/",

    "eurod":
        "https://www.eurod.com.tr/",

    "teve2":
        "https://www.teve2.com.tr/",

    "startv":
        "https://www.startv.com.tr/",

    "eurostar":
        "https://www.eurostartv.com.tr/",
}


# ============================================================
# HAUPTPLAYLIST
# ============================================================

PLAYLIST_FILE = os.path.join(
    "PStream",
    "2026",
    "playlist.m3u"
)


# ============================================================
# BROWSER
# ============================================================

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/128.0.0.0 "
    "Safari/537.36"
)


# ============================================================
# REGEX
# ============================================================

M3U8_REGEX = re.compile(
    r"""https?://[^\s"'<>\\]+?\.m3u8(?:\?[^\s"'<>\\]*)?""",
    re.IGNORECASE
)


RELATIVE_M3U8_REGEX = re.compile(
    r"""["']([^"']+?\.m3u8(?:\?[^"']*)?)["']""",
    re.IGNORECASE
)


# ============================================================
# URL
# ============================================================

def normalize_url(
    url,
    base_url=None
):

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

    if (
        base_url
        and not url.startswith(
            ("http://", "https://")
        )
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


# ============================================================
# BASE64
# ============================================================

def decode_base64(
    value
):

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


# ============================================================
# M3U8 FINDEN
# ============================================================

def extract_m3u8(
    text,
    base_url
):

    found = []

    if not text:
        return found

    def add_url(url):

        url = normalize_url(
            url,
            base_url
        )

        if (
            url
            and url not in found
        ):

            found.append(url)

    for match in M3U8_REGEX.findall(
        text
    ):

        add_url(match)

    for match in RELATIVE_M3U8_REGEX.findall(
        text
    ):

        add_url(match)

    cleaned = (
        text
        .replace("\\/", "/")
        .replace("\\u002F", "/")
        .replace("&amp;", "&")
    )

    for match in M3U8_REGEX.findall(
        cleaned
    ):

        add_url(match)

    # Base64 nur begrenzt prüfen,
    # damit die Suche schnell bleibt.

    tokens = re.findall(
        r"[A-Za-z0-9+/=_-]{40,}",
        text
    )

    for token in tokens[:40]:

        decoded = decode_base64(
            token
        )

        if not decoded:
            continue

        for match in M3U8_REGEX.findall(
            decoded
        ):

            add_url(match)

    return found


# ============================================================
# DUPLIKATE
# ============================================================

def unique_urls(
    urls
):

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


# ============================================================
# TOKEN
# ============================================================

def token_expired(
    url
):

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


def token_remaining_seconds(
    url
):

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

        return (
            expires
            - int(time.time())
        )

    except Exception:
        return None


# ============================================================
# MASTER PLAYLIST
# ============================================================

def is_master_playlist(
    url
):

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

    return bool(
        re.search(
            r"[/_-]"
            r"(playlist|master|index)"
            r"\.m3u8",
            u
        )
    )


# ============================================================
# QUALITÄT
# ============================================================

def quality_from_url(
    url
):

    u = url.lower()

    match = re.search(
        r"[/_-](\d{3,4})p\.m3u8",
        u
    )

    if match:
        return int(
            match.group(1)
        )

    for value in (
        1080,
        720,
        576,
        480,
        360
    ):

        if str(value) in u:
            return value

    if "_hd" in u:
        return 720

    if "_sd" in u:
        return 480

    return 0


# ============================================================
# STREAM BEWERTUNG
# ============================================================

def score_stream(
    url
):

    u = url.lower()

    score = 50

    if is_master_playlist(
        url
    ):

        score += 200

    score += (
        quality_from_url(url)
        // 10
    )

    if (
        "/live" in u
        or "-live" in u
        or "_live" in u
    ):

        score += 10

    if (
        "ercdn.net" in u
        or "daioncdn.net" in u
    ):

        score += 20

    remaining = (
        token_remaining_seconds(
            url
        )
    )

    if (
        remaining is not None
        and remaining > 60
    ):

        score += 20

    return score


# ============================================================
# UNNÖTIGE RESSOURCEN BLOCKIEREN
# ============================================================

def block_unnoetige_ressourcen(
    route
):

    request = route.request

    url = request.url.lower()

    resource_type = (
        request.resource_type
    )

    blockieren = (
        resource_type in {
            "image",
            "font",
            "stylesheet",
        }

        or any(
            x in url
            for x in (
                "google-analytics",
                "googletagmanager",
                "doubleclick",
                "facebook.net",
                "facebook.com/tr",
                "adsystem",
                "advertising",
                "adservice",
                "analytics",
                "hotjar",
                "clarity.ms",
                "segment.io",
            )
        )
    )

    if blockieren:

        route.abort()

    else:

        route.continue_()


# ============================================================
# STREAM VALIDIEREN
# ============================================================

def validate_stream(
    url,
    page,
    referer=None,
    timeout=5000
):

    if not url:
        return False

    if token_expired(url):
        return False

    try:

        headers = {
            "Accept":
                "application/vnd.apple.mpegurl,"
                "application/x-mpegURL,"
                "application/octet-stream,*/*"
        }

        if referer:

            headers["Referer"] = (
                referer
            )

            headers["Origin"] = (
                referer.rstrip("/")
            )

        response = page.request.get(
            url,
            timeout=timeout,
            fail_on_status_code=False,
            headers=headers
        )

        if response.status >= 400:

            print(
                f"      [X] "
                f"HTTP {response.status}"
            )

            return False

        content_type = (
            response.headers
            .get(
                "content-type",
                ""
            )
            .lower()
        )

        try:

            body = response.text()[
                :20000
            ]

        except Exception:

            body = ""

        if (
            "#EXTM3U" in body
            or "#EXT-X-" in body
            or "mpegurl" in content_type
            or "vnd.apple.mpegurl"
            in content_type
        ):

            print(
                "      [OK] "
                f"{url}"
            )

            return True

    except Exception as e:

        print(
            f"      [X] "
            f"{str(e)[:120]}"
        )

    return False


# ============================================================
# MASTER PLAYLIST PARSEN
# ============================================================

def parse_master_playlist(
    body,
    base_url
):

    if (
        not body
        or "#EXT-X-STREAM-INF"
        not in body
    ):

        return []

    variants = []

    lines = body.splitlines()

    for i, line in enumerate(
        lines
    ):

        if not line.strip().startswith(
            "#EXT-X-STREAM-INF"
        ):

            continue

        info = line.upper()

        bandwidth = 0

        resolution = ""

        resolution_score = 0

        match = re.search(
            r"BANDWIDTH=(\d+)",
            info
        )

        if match:

            bandwidth = int(
                match.group(1)
            )

        match = re.search(
            r"RESOLUTION=(\d+)X(\d+)",
            info
        )

        if match:

            width = int(
                match.group(1)
            )

            height = int(
                match.group(2)
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

                    "url":
                        variant_url,

                    "bandwidth":
                        bandwidth,

                    "resolution":
                        resolution,

                    "resolution_score":
                        resolution_score,

                    "quality":
                        quality_from_url(
                            variant_url
                        ),
                })

            break

    return variants


# ============================================================
# QUALITÄTSVARIANTEN HOLEN
# ============================================================

def collect_all_variants(
    master_url,
    page,
    referer=None
):

    try:

        headers = {
            "Accept":
                "application/vnd.apple.mpegurl,"
                "application/x-mpegURL,*/*"
        }

        if referer:

            headers["Referer"] = (
                referer
            )

            headers["Origin"] = (
                referer.rstrip("/")
            )

        response = page.request.get(
            master_url,
            timeout=7000,
            fail_on_status_code=False,
            headers=headers
        )

        if response.status >= 400:
            return []

        body = response.text()

        variants = (
            parse_master_playlist(
                body,
                master_url
            )
        )

        variants = [
            v
            for v in variants
            if not token_expired(
                v["url"]
            )
        ]

        variants.sort(
            key=lambda x: (
                x["resolution_score"],
                x["bandwidth"]
            ),
            reverse=True
        )

        return variants

    except Exception:

        return []


# ============================================================
# SEITE SCANNEN
# ============================================================

def scan_page(
    page,
    page_url
):

    found = []

    # Browser-Ressourcen

    try:

        entries = page.evaluate(
            "() => performance"
            ".getEntriesByType('resource')"
            ".map(x => x.name)"
        )

        for url in entries:

            if ".m3u8" in url.lower():

                found.extend(
                    extract_m3u8(
                        url,
                        page_url
                    )
                )

                found.append(
                    url
                )

    except Exception:
        pass

    # HTML

    try:

        html = page.content()

        found.extend(
            extract_m3u8(
                html,
                page_url
            )
        )

    except Exception:
        pass

    # Iframes nur wenn bisher nichts
    # gefunden wurde.

    if not found:

        try:

            for frame in page.frames:

                if (
                    not frame.url
                    or frame.url
                    == "about:blank"
                ):

                    continue

                try:

                    html = frame.content()

                    found.extend(
                        extract_m3u8(
                            html,
                            frame.url
                        )
                    )

                except Exception:

                    continue

        except Exception:
            pass

    return unique_urls(
        found
    )


# ============================================================
# SCHNELLER BROWSER-SCANNER
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
    print("=" * 65)
    print(
        f"[BROWSER] "
        f"{name}"
    )
    print(
        f"[URL] "
        f"{page_url}"
    )
    print("=" * 65)

    candidates = []

    stream_gefunden = False

    # --------------------------------------------------------
    # NETZWERK
    # --------------------------------------------------------

    def capture_response(
        response
    ):

        nonlocal stream_gefunden

        if stream_gefunden:
            return

        try:

            url = response.url

            if (
                ".m3u8"
                not in url.lower()
            ):

                return

            if token_expired(url):
                return

            candidates.append(
                url
            )

            print(
                "      [M3U8] "
                f"{url}"
            )

            stream_gefunden = True

        except Exception:
            pass

    page.on(
        "response",
        capture_response
    )

    # --------------------------------------------------------
    # SEITE ÖFFNEN
    # --------------------------------------------------------

    try:

        page.goto(
            page_url,
            wait_until="domcontentloaded",
            timeout=12000
        )

    except PlaywrightTimeoutError:

        print(
            "      [WARN] "
            "Seiten-Timeout."
        )

    except Exception as e:

        print(
            "[OPEN ERROR] "
            f"{str(e)[:150]}"
        )

    # --------------------------------------------------------
    # MAXIMAL 7 SEKUNDEN WARTEN
    # --------------------------------------------------------

    end_time = (
        time.monotonic()
        + 7
    )

    while (
        not stream_gefunden
        and time.monotonic()
        < end_time
    ):

        try:

            page.wait_for_timeout(
                200
            )

        except Exception:

            break

    # --------------------------------------------------------
    # FALLS NETZWERK NICHTS GEFUNDEN HAT
    # --------------------------------------------------------

    if not candidates:

        print(
            "      [SCAN] "
            "HTML / Ressourcen..."
        )

        try:

            candidates.extend(
                scan_page(
                    page,
                    page_url
                )
            )

        except Exception:
            pass

    candidates = unique_urls(
        candidates
    )

    candidates = [
        url
        for url in candidates
        if not token_expired(
            url
        )
    ]

    candidates.sort(
        key=score_stream,
        reverse=True
    )

    print(
        f"      [KANDIDATEN] "
        f"{len(candidates)}"
    )

    bester_stream = None

    # --------------------------------------------------------
    # STREAM PRÜFEN
    # --------------------------------------------------------

    for url in candidates:

        if validate_stream(
            url,
            page,
            referer=referer,
            timeout=5000
        ):

            bester_stream = url

            break

    try:

        page.remove_listener(
            "response",
            capture_response
        )

    except Exception:
        pass

    if not bester_stream:

        return None, []

    # --------------------------------------------------------
    # MASTER / QUALITÄTEN
    # --------------------------------------------------------

    varianten = (
        collect_all_variants(
            bester_stream,
            page,
            referer=referer
        )
    )

    return (
        bester_stream,
        varianten
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

        return (
            None,
            []
        )

    print(
        f"      [FALLBACK] "
        f"{channel_id}"
    )

    for url in urls:

        if token_expired(url):
            continue

        try:

            response = (
                request_context.get(
                    url,
                    timeout=6000,
                    fail_on_status_code=False
                )
            )

            if response.status >= 400:
                continue

            content_type = (
                response.headers
                .get(
                    "content-type",
                    ""
                )
                .lower()
            )

            try:

                body = response.text()[
                    :20000
                ]

            except Exception:

                body = ""

            if (
                "#EXTM3U"
                not in body
                and "#EXT-X-"
                not in body
                and "mpegurl"
                not in content_type
                and "vnd.apple.mpegurl"
                not in content_type
            ):

                continue

            variants = (
                parse_master_playlist(
                    body,
                    url
                )
            )

            print(
                "      [FALLBACK OK]"
            )

            return (
                url,
                variants
            )

        except Exception:
            continue

    return (
        None,
        []
    )


# ============================================================
# ORDNER
# ============================================================

def prepare_folders():

    os.makedirs(
        "streams",
        exist_ok=True
    )

    for filename in os.listdir(
        "streams"
    ):

        if (
            filename.endswith(".m3u")
            or filename.endswith(".m3u8")
            or filename.endswith(".error.txt")
            or filename in (
                "links.txt",
                "github_links.txt"
            )
        ):

            try:

                os.remove(
                    os.path.join(
                        "streams",
                        filename
                    )
                )

            except Exception:
                pass


# ============================================================
# EINZELNE M3U
# ============================================================

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


# ============================================================
# QUALITÄTSPLAYLIST
# ============================================================

def build_quality_playlist(
    channel,
    variants
):

    lines = [
        "#EXTM3U",
        "#EXT-X-VERSION:3"
    ]

    for variant in variants:

        bandwidth = (
            variant.get(
                "bandwidth"
            )
            or 1000000
        )

        resolution = (
            variant.get(
                "resolution"
            )
            or ""
        )

        if not resolution:

            quality = variant.get(
                "quality",
                0
            )

            if quality >= 720:

                resolution = (
                    "1280x720"
                )

            elif quality >= 576:

                resolution = (
                    "1024x576"
                )

            elif quality >= 480:

                resolution = (
                    "854x480"
                )

            else:

                resolution = (
                    "640x360"
                )

        lines.append(
            "#EXT-X-STREAM-INF:"
            f"PROGRAM-ID=1,"
            f"BANDWIDTH={bandwidth},"
            f"RESOLUTION={resolution}"
        )

        lines.append(
            variant["url"]
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
        return

    path = os.path.join(
        "streams",
        f"{channel_id}_all.m3u8"
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            build_quality_playlist(
                channel,
                variants
            )
        )


# ============================================================
# FEHLERDATEI
# ============================================================

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
            f"Kanal: "
            f"{channel['name']}\n"
            f"URL: "
            f"{channel['url']}\n"
            "Status: "
            "M3U8 nicht gefunden\n"
        )


# ============================================================
# PLAYLIST-ERKENNUNG
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
            "show tv" in text
            or "showtv" in text
        )

    if cid == "showturk":

        return (
            "show türk" in text
            or "showturk" in text
        )

    if cid == "showmax":

        return (
            "showmax" in text
        )

    if cid == "nowtv":

        return (
            'tvg-id="fox.tr"'
            in text
            or ",now" in text
            or ", now" in text
            or "now tv" in text
        )

    if cid == "atv":

        return (
            'tvg-id="atv.tr"'
            in text
            or "atv hd" in text
        )

    if cid == "tv8":

        return (
            'tvg-id="tv8.hd.tr"'
            in text
            or 'tvg-id="tv8.tr"'
            in text
            or ",tv8" in text
            or ", tv8" in text
        )

    if cid == "tv8int":

        return (
            "tv8int" in text
            or "tv8 international"
            in text
        )

    if cid == "kanald":

        return (
            "kanal d" in text
            or "kanald" in text
        )

    if cid == "eurod":

        return (
            "euro d" in text
            or "eurod" in text
        )

    if cid == "teve2":

        return (
            "teve2" in text
        )

    if cid == "startv":

        return (
            "star tv" in text
            or "startv" in text
        )

    if cid == "eurostar":

        return (
            "eurostar" in text
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
# HAUPTPLAYLIST AKTUALISIEREN
# ============================================================

def update_existing_playlist(
    results
):

    print("")
    print("=" * 65)
    print(
        "[PLAYLIST] "
        "Hauptplaylist wird aktualisiert"
    )
    print("=" * 65)

    if not os.path.exists(
        PLAYLIST_FILE
    ):

        print(
            "[FEHLER] "
            f"{PLAYLIST_FILE} "
            "nicht gefunden."
        )

        return

    try:

        with open(
            PLAYLIST_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            lines = f.readlines()

    except Exception as e:

        print(
            f"[FEHLER] "
            f"{e}"
        )

        return

    aktualisiert = 0

    for cid, data in results.items():

        if not data:
            continue

        new_url = data.get(
            "master"
        )

        if not new_url:
            continue

        for i, line in enumerate(
            lines
        ):

            if not playlist_channel_matches(
                line,
                cid
            ):

                continue

            for j in range(
                i + 1,
                min(
                    i + 20,
                    len(lines)
                )
            ):

                if lines[j].startswith(
                    "#EXTINF"
                ):

                    break

                if not is_active_stream_line(
                    lines[j]
                ):

                    continue

                old_url = (
                    lines[j].strip()
                )

                if old_url != new_url:

                    lines[j] = (
                        new_url
                        + "\n"
                    )

                    print(
                        f"[UPDATE] "
                        f"{CHANNELS[cid]['name']}"
                    )

                    print(
                        f"   ALT: "
                        f"{old_url}"
                    )

                    print(
                        f"   NEU: "
                        f"{new_url}"
                    )

                    aktualisiert += 1

                break

            break

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
            f"[FEHLER] "
            f"Playlist schreiben: "
            f"{e}"
        )

        return

    print(
        f"[PLAYLIST] "
        f"{aktualisiert} "
        f"Einträge aktualisiert."
    )


# ============================================================
# ALLE AUSGABEDATEIEN
# ============================================================

def write_all_m3u(
    results
):

    all_lines = [
        "#EXTM3U"
    ]

    for cid, channel in (
        CHANNELS.items()
    ):

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

        write_m3u(
            cid,
            channel,
            master
        )

        variants = data.get(
            "variants",
            []
        )

        if variants:

            write_quality_playlist(
                cid,
                channel,
                variants
            )

        all_lines.append(
            f'#EXTINF:-1 '
            f'tvg-id="{cid}" '
            f'tvg-name="{channel["name"]}" '
            f'group-title="Turkiye",'
            f'{channel["name"]}'
        )

        all_lines.append(
            master
        )

    with open(
        os.path.join(
            "streams",
            "all.m3u"
        ),
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            "\n".join(
                all_lines
            )
            + "\n"
        )

    with open(
        os.path.join(
            "streams",
            "links.txt"
        ),
        "w",
        encoding="utf-8"
    ) as f:

        for cid, channel in (
            CHANNELS.items()
        ):

            data = results.get(
                cid
            )

            if (
                data
                and data.get("master")
            ):

                f.write(
                    f"# {channel['name']}\n"
                    f"{data['master']}\n\n"
                )

    # Hauptplaylist aktualisieren
    update_existing_playlist(
        results
    )


# ============================================================
# HAUPTPROGRAMM
# ============================================================

def main():

    start_time = (
        time.monotonic()
    )

    print("")
    print("=" * 65)
    print(
        "TURK TV LIVE SCANNER"
    )
    print(
        "SCHNELLE VERSION"
    )
    print("=" * 65)

    print(
        f"Sender: "
        f"{len(CHANNELS)}"
    )

    print(
        f"Playlist: "
        f"{PLAYLIST_FILE}"
    )

    print("=" * 65)

    prepare_folders()

    results = {}

    with sync_playwright() as p:

        # ----------------------------------------------------
        # CHROMIUM
        # ----------------------------------------------------

        browser = p.chromium.launch(

            headless=True,

            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-software-rasterizer",
                "--autoplay-policy="
                "no-user-gesture-required",
            ]
        )

        # ----------------------------------------------------
        # BROWSER-CONTEXT
        # ----------------------------------------------------

        context = (
            browser.new_context(

                ignore_https_errors=True,

                user_agent=USER_AGENT,

                viewport={
                    "width": 1280,
                    "height": 720
                },

                locale="tr-TR",

                timezone_id=(
                    "Europe/Istanbul"
                ),

                extra_http_headers={

                    "Accept-Language":
                        "tr-TR,tr;q=0.9,en;q=0.8"
                }
            )
        )

        # Unnötige Ressourcen blockieren.
        context.route(
            "**/*",
            block_unnoetige_ressourcen
        )

        # ----------------------------------------------------
        # REQUEST-CONTEXT
        # ----------------------------------------------------

        request_context = (
            p.request.new_context(

                ignore_https_errors=True,

                extra_http_headers={

                    "User-Agent":
                        USER_AGENT,

                    "Accept":
                        "application/vnd.apple.mpegurl,"
                        "application/x-mpegURL,*/*"
                }
            )
        )

        try:

            # ------------------------------------------------
            # SENDER DURCHLAUFEN
            # ------------------------------------------------

            for cid, channel in (
                CHANNELS.items()
            ):

                sender_start = (
                    time.monotonic()
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
                        channel
                    )

                except Exception as e:

                    print(
                        f"[BROWSER FEHLER] "
                        f"{channel['name']}: "
                        f"{str(e)[:150]}"
                    )

                finally:

                    try:
                        page.close()
                    except Exception:
                        pass

                # ------------------------------------------------
                # FALLBACK
                # ------------------------------------------------

                if not master:

                    print(
                        f"[BROWSER] "
                        f"{channel['name']} "
                        f"nicht gefunden."
                    )

                    referer = (
                        REFERERS.get(
                            cid,
                            channel["url"]
                        )
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
                                    "application/x-mpegURL,*/*",

                                "Referer":
                                    referer,

                                "Origin":
                                    referer.rstrip("/")
                            }
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
                            f"[FALLBACK FEHLER] "
                            f"{str(e)[:150]}"
                        )

                results[cid] = {

                    "master":
                        master,

                    "variants":
                        variants
                }

                dauer = (
                    time.monotonic()
                    - sender_start
                )

                if master:

                    print(
                        f"[OK] "
                        f"{channel['name']} "
                        f"– "
                        f"{dauer:.1f} Sekunden"
                    )

                else:

                    print(
                        f"[X] "
                        f"{channel['name']} "
                        f"– "
                        f"{dauer:.1f} Sekunden"
                    )

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

    # ========================================================
    # DATEIEN SCHREIBEN
    # ========================================================

    write_all_m3u(
        results
    )

    # ========================================================
    # ERGEBNIS
    # ========================================================

    erfolgreich = sum(
        1
        for data in results.values()
        if data.get("master")
    )

    fehlgeschlagen = (
        len(CHANNELS)
        - erfolgreich
    )

    gesamtzeit = (
        time.monotonic()
        - start_time
    )

    # Fehlerdateien
    for cid, channel in (
        CHANNELS.items()
    ):

        data = results.get(
            cid
        )

        if not data or not data.get(
            "master"
        ):

            write_error(
                cid,
                channel
            )

    print("")
    print("=" * 65)
    print(
        "SCAN FERTIG"
    )
    print("=" * 65)

    print(
        f"Erfolgreich: "
        f"{erfolgreich}/"
        f"{len(CHANNELS)}"
    )

    print(
        f"Nicht gefunden: "
        f"{fehlgeschlagen}"
    )

    print(
        f"Gesamtzeit: "
        f"{gesamtzeit:.1f} Sekunden"
    )

    print("=" * 65)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()
