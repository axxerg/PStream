import os
import re
import time
import base64
from urllib.parse import (
    urljoin,
    urlparse,
    parse_qs,
    unquote,
)

from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
)


# ============================================================
# KONFIGURATION
# ============================================================

CHANNELS = {
    "showtv": {
        "name": "Show TV",
        "url": "https://www.showtv.com.tr/canli-yayin",
    },
    "showturk": {
        "name": "ShowTurk",
        "url": "https://www.showturk.com.tr/canli-yayin",
    },
    "showmax": {
        "name": "Showmax",
        "url": "https://www.showmax.com.tr/",
    },
    "nowtv": {
        "name": "NOW TV",
        "url": "https://www.nowtv.com.tr/canli-yayin",
    },
    "atv": {
        "name": "ATV",
        "url": "https://www.atv.com.tr/canli-yayin",
    },
    "atv": {
        "name": "cnn",
        "url": "https://www.cnnturk.com/canli-yayin",
    },
    "tv8": {
        "name": "TV8",
        "url": "https://www.tv8.com.tr/canli-yayin",
    },
    "tv8int": {
        "name": "TV8 International",
        "url": "https://www.tv8.com.tr/tv8-international",
    },
    "kanald": {
        "name": "Kanal D",
        "url": "https://www.kanald.com.tr/canli-yayin",
    },
    "eurod": {
        "name": "Euro D",
        "url": "https://www.eurod.com.tr/canli-yayin",
    },
    "teve2": {
        "name": "Teve2",
        "url": "https://www.teve2.com.tr/canli-yayin",
    },
    "startv": {
        "name": "Star TV",
        "url": "https://www.startv.com.tr/canli-yayin",
    },
    "eurostar": {
        "name": "Eurostar TV",
        "url": "https://www.eurostartv.com.tr/canli-izle",
    },
}


# ============================================================
# FALLBACK-STREAMS
# ============================================================

FALLBACK_STREAMS = {
    "showtv": [
        "https://ciner-live.ercdn.net/showtv/playlist.m3u8",
    ],

    "showturk": [
        "https://ciner-live.ercdn.net/showturk/playlist.m3u8",
    ],

    "showmax": [
        "https://ciner-live.ercdn.net/showmax/playlist.m3u8",
    ],

    "nowtv": [
        "https://ciner-live.ercdn.net/nowtv/playlist.m3u8",
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
    "showtv": "https://www.showtv.com.tr/",
    "showturk": "https://www.showturk.com.tr/",
    "showmax": "https://www.showmax.com.tr/",
    "nowtv": "https://www.nowtv.com.tr/",
    "atv": "https://www.atv.com.tr/",
    "cnn"": "https://www.cnnturk.com/canli-yayin/",
    "tv8": "https://www.tv8.com.tr/",
    "tv8int": "https://www.tv8.com.tr/",
    "kanald": "https://www.kanald.com.tr/",
    "eurod": "https://www.eurod.com.tr/",
    "teve2": "https://www.teve2.com.tr/",
    "startv": "https://www.startv.com.tr/",
    "eurostar": "https://www.eurostartv.com.tr/",
}


# ============================================================
# DATEIEN
# ============================================================

# WICHTIG:
# Das Repository heißt bereits PStream.
# Deshalb ist der korrekte Pfad:
#
# 2026/playlist.m3u
#
# und NICHT:
#
# PStream/2026/playlist.m3u

PLAYLIST_FILE = os.path.join(
    "2026",
    "playlist.m3u",
)


USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)


# ============================================================
# REGEX
# ============================================================

M3U8_REGEX = re.compile(
    r"""https?://[^\s"'<>\\]+?\.m3u8(?:\?[^\s"'<>\\]*)?""",
    re.IGNORECASE,
)


RELATIVE_M3U8_REGEX = re.compile(
    r"""["']([^"']+?\.m3u8(?:\?[^"']*)?)["']""",
    re.IGNORECASE,
)


# ============================================================
# URL-FUNKTIONEN
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

    if (
        base_url
        and not url.startswith(
            ("http://", "https://")
        )
    ):
        url = urljoin(
            base_url,
            url,
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

        value += "=" * (-len(value) % 4)

        decoded = base64.b64decode(
            value,
            validate=False,
        ).decode(
            "utf-8",
            errors="ignore",
        )

        if ".m3u8" in decoded.lower():
            return decoded

    except Exception:
        pass

    return None


# ============================================================
# M3U8 ERKENNUNG
# ============================================================

def extract_m3u8(text, base_url):
    if not text:
        return []

    found = []

    def add(url):
        url = normalize_url(
            url,
            base_url,
        )

        if url and url not in found:
            found.append(url)

    for match in M3U8_REGEX.findall(text):
        add(match)

    for match in RELATIVE_M3U8_REGEX.findall(text):
        add(match)

    cleaned = (
        text
        .replace("\\/", "/")
        .replace("\\u002F", "/")
        .replace("&amp;", "&")
    )

    for match in M3U8_REGEX.findall(cleaned):
        add(match)

    # Nur die ersten Base64-Kandidaten prüfen.
    for token in re.findall(
        r"[A-Za-z0-9+/=_-]{40,}",
        text,
    )[:40]:

        decoded = decode_base64(token)

        if not decoded:
            continue

        for match in M3U8_REGEX.findall(decoded):
            add(match)

    return found


# ============================================================
# ATV SECURE-URL AUFLÖSEN
# ============================================================

def extract_atv_m3u8_from_secure(
    text,
    base_url,
):
    """
    ATV liefert zunächst eine Secure-URL:

    https://securevideotoken.tmgrup.com.tr/webtv/secure?...

    Diese URL soll NICHT in die Playlist geschrieben werden.

    Gesucht wird stattdessen die echte:

    https://trkvz-live.ercdn.net/atvavrupa/...

    M3U8-Adresse.
    """

    if not text:
        return []

    found = []

    def add(url):
        url = normalize_url(
            url,
            base_url,
        )

        if not url:
            return

        if "trkvz-live.ercdn.net" not in url.lower():
            return

        if ".m3u8" not in url.lower():
            return

        if url not in found:
            found.append(url)

    cleaned = (
        str(text)
        .replace("\\/", "/")
        .replace("\\u002F", "/")
        .replace("&amp;", "&")
    )

    # Direkte trkvz-live URLs finden.
    for match in M3U8_REGEX.findall(cleaned):
        add(match)

    # Query-Parameter der Secure-URL prüfen.
    try:
        parsed = urlparse(base_url)
        query = parse_qs(
            parsed.query
        )

        for key in (
            "url",
            "url2",
        ):
            for value in query.get(
                key,
                [],
            ):

                value = (
                    value
                    .replace("\\/", "/")
                    .replace("\\u002F", "/")
                )

                try:
                    value = unquote(value)
                except Exception:
                    pass

                add(value)

    except Exception:
        pass

    # URL-Parameter direkt aus HTML/Text lesen.
    for match in re.findall(
        r"""(?:url|url2)=([^&\s"'<>]+)""",
        cleaned,
        flags=re.IGNORECASE,
    ):

        try:
            add(
                unquote(match)
            )
        except Exception:
            pass

    return unique_urls(found)


# ============================================================
# URL-LISTEN
# ============================================================

def unique_urls(urls):
    result = []
    seen = set()

    for url in urls:

        if not url:
            continue

        url = url.strip()

        if url not in seen:
            seen.add(url)
            result.append(url)

    return result


# ============================================================
# TOKEN
# ============================================================

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

        return (
            expires
            <= int(time.time()) + 30
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

        return (
            expires
            - int(time.time())
        )

    except Exception:
        return None


# ============================================================
# STREAM-BEWERTUNG
# ============================================================

def is_master_playlist(url):
    u = url.lower()

    if re.search(
        r"[/_-]\d{3,4}p\.m3u8",
        u,
    ):
        return False

    if re.search(
        r"_hd\.m3u8|_sd\.m3u8|_\d{3,4}\.m3u8",
        u,
    ):
        return False

    return bool(
        re.search(
            r"[/_-](playlist|master|index)\.m3u8",
            u,
        )
    )


def quality_from_url(url):
    u = url.lower()

    match = re.search(
        r"[/_-](\d{3,4})p\.m3u8",
        u,
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
        360,
    ):
        if str(value) in u:
            return value

    if "_hd" in u:
        return 720

    if "_sd" in u:
        return 480

    return 0


def score_stream(url):
    u = url.lower()

    score = 50

    if is_master_playlist(url):
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

    remaining = token_remaining_seconds(
        url
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

def block_unnoetige_ressourcen(route):
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
    timeout=7000,
):
    if not url:
        return False

    if token_expired(url):
        return False

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
            timeout=timeout,
            fail_on_status_code=False,
            headers=headers,
        )

        if response.status >= 400:
            print(
                f"      [X] HTTP "
                f"{response.status}"
            )
            return False

        content_type = (
            response.headers.get(
                "content-type",
                "",
            )
            .lower()
        )

        try:
            body = response.text()[:20000]
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
                f"      [OK] {url}"
            )

            return True

    except Exception as e:

        print(
            f"      [X] "
            f"{str(e)[:120]}"
        )

    return False


# ============================================================
# MASTER PLAYLIST
# ============================================================

def parse_master_playlist(
    body,
    base_url,
):
    if (
        not body
        or "#EXT-X-STREAM-INF"
        not in body
    ):
        return []

    variants = []

    lines = body.splitlines()

    for i, line in enumerate(lines):

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
            info,
        )

        if match:
            bandwidth = int(
                match.group(1)
            )

        match = re.search(
            r"RESOLUTION=(\d+)X(\d+)",
            info,
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
                base_url,
            )

            if variant_url:

                variants.append(
                    {
                        "url": variant_url,
                        "bandwidth": bandwidth,
                        "resolution": resolution,
                        "resolution_score":
                            resolution_score,
                        "quality":
                            quality_from_url(
                                variant_url
                            ),
                    }
                )

            break

    return variants


def collect_all_variants(
    master_url,
    page,
    referer=None,
):
    try:

        headers = {
            "Accept": (
                "application/vnd.apple.mpegurl,"
                "application/x-mpegURL,*/*"
            )
        }

        if referer:
            headers["Referer"] = referer
            headers["Origin"] = (
                referer.rstrip("/")
            )

        response = page.request.get(
            master_url,
            timeout=7000,
            fail_on_status_code=False,
            headers=headers,
        )

        if response.status >= 400:
            return []

        body = response.text()

        variants = parse_master_playlist(
            body,
            master_url,
        )

        if not variants:
            return []

        # Nicht jede Variante einzeln validieren.
        # Das spart sehr viel Zeit.
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
                x["bandwidth"],
            ),
            reverse=True,
        )

        return variants

    except Exception:
        return []


# ============================================================
# SEITE SCANNEN
# ============================================================

def scan_page(
    page,
    page_url,
):
    found = []

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
                        page_url,
                    )
                )

                found.append(url)

    except Exception:
        pass

    try:

        html = page.content()

        found.extend(
            extract_m3u8(
                html,
                page_url,
            )
        )

    except Exception:
        pass

    # Nur Frames prüfen,
    # wenn bisher nichts gefunden wurde.
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
                            frame.url,
                        )
                    )

                except Exception:
                    continue

        except Exception:
            pass

    return unique_urls(found)


# ============================================================
# SCHNELLER BROWSER-SCANNER
# ============================================================

def browser_find_stream(
    page,
    channel_id,
    channel,
):
    name = channel["name"]

    page_url = channel["url"]

    referer = REFERERS.get(
        channel_id,
        page_url,
    )

    print("")
    print("=" * 65)
    print(
        f"[BROWSER] {name}"
    )
    print(
        f"[URL] {page_url}"
    )
    print("=" * 65)

    candidates = []

    gefunden = False

    def capture_response(response):
        nonlocal gefunden

        if gefunden:
            return

        try:

            url = response.url

            lower_url = url.lower()

            # ==================================================
            # ATV SONDERBEHANDLUNG
            # ==================================================
            #
            # ATV liefert zunächst:
            #
            # securevideotoken.tmgrup.com.tr
            #
            # Diese URL darf NICHT als Ergebnis gespeichert
            # werden.
            #
            # Wir suchen stattdessen:
            #
            # trkvz-live.ercdn.net
            #
            # inklusive Token ?st=...&e=...
            #

            if (
                channel_id == "atv"
                and
                "securevideotoken.tmgrup.com.tr"
                in lower_url
            ):

                try:
                    secure_body = (
                        response.text()
                    )
                except Exception:
                    secure_body = ""

                atv_urls = (
                    extract_atv_m3u8_from_secure(
                        secure_body,
                        url,
                    )
                )

                # Zusätzlich url/url2 aus
                # der Secure-URL prüfen.
                atv_urls.extend(
                    extract_atv_m3u8_from_secure(
                        url,
                        url,
                    )
                )

                atv_urls = unique_urls(
                    atv_urls
                )

                if atv_urls:

                    candidates.extend(
                        atv_urls
                    )

                    for atv_url in atv_urls:

                        print(
                            "      [ATV M3U8] "
                            f"{atv_url}"
                        )

                    gefunden = True

                return

            # ==================================================
            # NORMALE M3U8
            # ==================================================

            if (
                ".m3u8" in lower_url
                and not token_expired(url)
            ):

                candidates.append(url)

                print(
                    f"      [M3U8] {url}"
                )

                gefunden = True

        except Exception:
            pass

    page.on(
        "response",
        capture_response,
    )

    try:

        page.goto(
            page_url,
            wait_until="domcontentloaded",
            timeout=12000,
        )

    except PlaywrightTimeoutError:

        print(
            "      [WARN] "
            "Seiten-Timeout."
        )

    except Exception as e:

        print(
            "      [OPEN ERROR] "
            f"{str(e)[:150]}"
        )

    # Höchstens 7 Sekunden warten.
    # Sobald M3U8 gefunden wurde:
    # sofort weiter.
    end_time = (
        time.monotonic()
        + 7
    )

    while (
        not gefunden
        and time.monotonic()
        < end_time
    ):

        try:
            page.wait_for_timeout(
                200
            )
        except Exception:
            break

    # Falls Netzwerk nichts gefunden hat:
    if not candidates:

        candidates.extend(
            scan_page(
                page,
                page_url,
            )
        )

    candidates = unique_urls(
        candidates
    )

    # ========================================================
    # ATV MASTER -> 576p AUFLÖSEN
    # ========================================================

    if channel_id == "atv":

        atv_variants = []

        for candidate in list(
            candidates
        ):

            if (
                "trkvz-live.ercdn.net"
                not in candidate.lower()
            ):
                continue

            try:

                variants = (
                    collect_all_variants(
                        candidate,
                        page,
                        referer=referer,
                    )
                )

                atv_variants.extend(
                    v.get("url")
                    for v in variants
                    if v.get("url")
                )

            except Exception:
                continue

        candidates.extend(
            atv_variants
        )

        candidates = unique_urls(
            candidates
        )

        # ====================================================
        # ATV QUALITÄTSREIHENFOLGE
        # ====================================================
        #
        # 1. 576p
        # 2. 720p
        # 3. 1080p
        # 4. andere Varianten
        # 5. Master
        #

        def atv_score(url):

            quality = (
                quality_from_url(url)
            )

            score = 0

            if (
                "trkvz-live.ercdn.net"
                in url.lower()
            ):
                score += 1000

            if quality == 576:
                score += 500

            elif quality == 720:
                score += 300

            elif quality == 1080:
                score += 200

            if is_master_playlist(
                url
            ):
                score -= 400

            if (
                token_remaining_seconds(
                    url
                )
                is not None
            ):
                score += 50

            return score

        candidates.sort(
            key=atv_score,
            reverse=True,
        )

    # ========================================================
    # ABGELAUFENE URLS ENTFERNEN
    # ========================================================

    candidates = [
        url
        for url in candidates
        if not token_expired(url)
    ]

    # Andere Sender normal bewerten.
    if channel_id != "atv":

        candidates.sort(
            key=score_stream,
            reverse=True,
        )

    print(
        f"      [KANDIDATEN] "
        f"{len(candidates)}"
    )

    bester_stream = None

    for url in candidates:

        if validate_stream(
            url,
            page,
            referer=referer,
            timeout=5000,
        ):

            bester_stream = url
            break

    try:

        page.remove_listener(
            "response",
            capture_response,
        )

    except Exception:
        pass

    if not bester_stream:
        return None, []

    # ========================================================
    # ATV SICHERSTELLEN:
    # KEINE SECURE-URL ALS AUSGABE
    # ========================================================

    if (
        channel_id == "atv"
        and
        "securevideotoken.tmgrup.com.tr"
        in bester_stream.lower()
    ):

        print(
            "      [ATV] "
            "Secure-URL verworfen."
        )

        return None, []

    varianten = (
        collect_all_variants(
            bester_stream,
            page,
            referer=referer,
        )
    )

    # ========================================================
    # ATV: 576p AUS MASTER AUSWÄHLEN
    # ========================================================

    if (
        channel_id == "atv"
        and varianten
    ):

        passende_576 = [
            v
            for v in varianten
            if v.get("quality") == 576
        ]

        if passende_576:

            passende_576.sort(
                key=lambda x: (
                    x.get(
                        "resolution_score",
                        0,
                    ),
                    x.get(
                        "bandwidth",
                        0,
                    ),
                ),
                reverse=True,
            )

            bester_stream = (
                passende_576[0]["url"]
            )

            print(
                "      [ATV] "
                "576p ausgewählt:"
            )

            print(
                f"      {bester_stream}"
            )

    return (
        bester_stream,
        varianten,
    )


# ============================================================
# FALLBACK
# ============================================================

def fallback_find(
    request_context,
    channel_id,
):
    urls = FALLBACK_STREAMS.get(
        channel_id,
        [],
    )

    if not urls:
        return None, []

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
                    fail_on_status_code=False,
                )
            )

            if response.status >= 400:
                continue

            content_type = (
                response.headers.get(
                    "content-type",
                    "",
                )
                .lower()
            )

            body = ""

            try:
                body = (
                    response.text()[
                        :20000
                    ]
                )
            except Exception:
                pass

            if (
                "#EXTM3U" not in body
                and "#EXT-X-" not in body
                and "mpegurl"
                not in content_type
                and "vnd.apple.mpegurl"
                not in content_type
            ):
                continue

            variants = (
                parse_master_playlist(
                    body,
                    url,
                )
            )

            # Wenn es eine Master-Playlist ist:
            # Varianten zurückgeben.
            if variants:

                variants = [
                    v
                    for v in variants
                    if not token_expired(
                        v["url"]
                    )
                ]

                variants.sort(
                    key=lambda x: (
                        x[
                            "resolution_score"
                        ],
                        x[
                            "bandwidth"
                        ],
                    ),
                    reverse=True,
                )

                return (
                    url,
                    variants,
                )

            # Direkte M3U8.
            if (
                "#EXTM3U" in body
                or "#EXT-X-"
                in body
            ):

                return (
                    url,
                    [],
                )

        except Exception:
            continue

    return None, []


# ============================================================
# ORDNER / DATEIEN
# ============================================================

def prepare_folders():

    os.makedirs(
        "streams",
        exist_ok=True,
    )

    for filename in os.listdir(
        "streams"
    ):

        if (
            filename.endswith(".m3u")
            or filename.endswith(".m3u8")
            or filename.endswith(
                ".error.txt"
            )
            or filename in (
                "links.txt",
                "github_links.txt",
            )
        ):

            try:

                os.remove(
                    os.path.join(
                        "streams",
                        filename,
                    )
                )

            except Exception:
                pass


def write_m3u(
    channel_id,
    channel,
    stream_url,
):
    path = os.path.join(
        "streams",
        f"{channel_id}.m3u",
    )

    content = (
        "#EXTM3U\n"
        f'#EXTINF:-1 tvg-id="{channel_id}" '
        f'tvg-name="{channel["name"]}" '
        f'group-title="Turkiye",'
        f'{channel["name"]}\n'
        f"{stream_url}\n"
    )

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as f:

        f.write(content)


def build_quality_playlist(
    channel,
    variants,
):
    lines = [
        "#EXTM3U",
        "#EXT-X-VERSION:3",
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
                0,
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
            "PROGRAM-ID=1,"
            f"BANDWIDTH={bandwidth},"
            f"RESOLUTION={resolution}",
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
    variants,
):
    if not variants:
        return

    path = os.path.join(
        "streams",
        f"{channel_id}_all.m3u8",
    )

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as f:

        f.write(
            build_quality_playlist(
                channel,
                variants,
            )
        )


def write_error(
    channel_id,
    channel,
):
    path = os.path.join(
        "streams",
        f"{channel_id}.error.txt",
    )

    with open(
        path,
        "w",
        encoding="utf-8",
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
    cid,
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
            'tvg-id="fox.tr"' in text
            or ",now" in text
            or ", now" in text
            or "now tv" in text
        )

    if cid == "atv":
        return (
            'tvg-id="atv.tr"' in text
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
    line,
):
    stripped = line.strip()

    return (
        bool(stripped)
        and not stripped.startswith(
            "#"
        )
        and (
            stripped.startswith(
                "http://"
            )
            or stripped.startswith(
                "https://"
            )
        )
    )


# ============================================================
# HAUPTPLAYLIST AKTUALISIEREN
# ============================================================

def update_existing_playlist(
    results,
):
    print("")
    print("=" * 65)
    print(
        "[PLAYLIST] Hauptplaylist"
    )
    print("=" * 65)

    if not os.path.exists(
        PLAYLIST_FILE
    ):

        print(
            "[FEHLER] Nicht gefunden: "
            f"{PLAYLIST_FILE}"
        )

        return

    try:

        with open(
            PLAYLIST_FILE,
            "r",
            encoding="utf-8",
        ) as f:

            lines = f.readlines()

    except Exception as e:

        print(
            "[FEHLER] "
            f"Playlist lesen: {e}"
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

        # Secure-URLs niemals übernehmen.
        if (
            "securevideotoken.tmgrup.com.tr"
            in new_url.lower()
        ):
            print(
                f"[SKIP] "
                f"{CHANNELS[cid]['name']}: "
                "Secure-URL"
            )
            continue

        for i, line in enumerate(
            lines
        ):

            if not playlist_channel_matches(
                line,
                cid,
            ):
                continue

            for j in range(
                i + 1,
                min(
                    i + 20,
                    len(lines),
                ),
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
                        "[UPDATE] "
                        f"{CHANNELS[cid]['name']}"
                    )

                    print(
                        f"        ALT: "
                        f"{old_url}"
                    )

                    print(
                        f"        NEU: "
                        f"{new_url}"
                    )

                    aktualisiert += 1

                break

            break

    try:

        with open(
            PLAYLIST_FILE,
            "w",
            encoding="utf-8",
        ) as f:

            f.writelines(lines)

    except Exception as e:

        print(
            "[FEHLER] "
            f"Playlist schreiben: {e}"
        )

        return

    print(
        "[PLAYLIST] "
        f"{aktualisiert} Einträge aktualisiert."
    )


# ============================================================
# AUSGABEDATEIEN
# ============================================================

def write_all_m3u(
    results,
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
            master,
        )

        variants = data.get(
            "variants",
            [],
        )

        if variants:

            write_quality_playlist(
                cid,
                channel,
                variants,
            )

        all_lines.append(
            f'#EXTINF:-1 tvg-id="{cid}" '
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
            "all.m3u",
        ),
        "w",
        encoding="utf-8",
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
            "links.txt",
        ),
        "w",
        encoding="utf-8",
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

    update_existing_playlist(
        results
    )


# ============================================================
# HAUPTPROGRAMM
# ============================================================

def main():

    start = time.monotonic()

    print("")
    print("=" * 65)
    print(
        "TURK TV LIVE SCANNER – SCHNELL"
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

        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-software-rasterizer",
                "--autoplay-policy=no-user-gesture-required",
            ],
        )

        context = browser.new_context(
            ignore_https_errors=True,
            user_agent=USER_AGENT,
            viewport={
                "width": 1280,
                "height": 720,
            },
            locale="tr-TR",
            timezone_id="Europe/Istanbul",
            extra_http_headers={
                "Accept-Language":
                    "tr-TR,tr;q=0.9,en;q=0.8",
            },
        )

        # Unnötige Ressourcen blockieren.
        context.route(
            "**/*",
            block_unnoetige_ressourcen,
        )

        request_context = (
            p.request.new_context(
                ignore_https_errors=True,
                extra_http_headers={
                    "User-Agent":
                        USER_AGENT,
                    "Accept": (
                        "application/vnd.apple.mpegurl,"
                        "application/x-mpegURL,*/*"
                    ),
                },
            )
        )

        try:

            for cid, channel in (
                CHANNELS.items()
            ):

                sender_start = (
                    time.monotonic()
                )

                page = (
                    context.new_page()
                )

                try:

                    print("")
                    print(
                        "#" * 65
                    )

                    print(
                        f"# "
                        f"{channel['name']}"
                    )

                    print(
                        "#" * 65
                    )

                    master = None
                    variants = []

                    # ==================================================
                    # 1. BROWSER
                    # ==================================================

                    try:

                        (
                            master,
                            variants,
                        ) = browser_find_stream(
                            page,
                            cid,
                            channel,
                        )

                    except Exception as e:

                        print(
                            "[BROWSER FEHLER] "
                            f"{str(e)[:200]}"
                        )

                    # ==================================================
                    # 2. FALLBACK
                    # ==================================================

                    if not master:

                        print(
                            "      "
                            "[INFO] "
                            "Browser ohne Ergebnis."
                        )

                        (
                            master,
                            variants,
                        ) = fallback_find(
                            request_context,
                            cid,
                        )

                    # ==================================================
                    # 3. ERGEBNIS
                    # ==================================================

                    if master:

                        # ATV Secure-URL endgültig verhindern.
                        if (
                            cid == "atv"
                            and
                            "securevideotoken.tmgrup.com.tr"
                            in master.lower()
                        ):

                            print(
                                "      "
                                "[ATV] "
                                "Secure-URL verworfen."
                            )

                            master = None
                            variants = []

                    if master:

                        print(
                            ""
                            "      "
                            "[ERFOLG]"
                        )

                        print(
                            f"      {master}"
                        )

                        results[cid] = {
                            "master": master,
                            "variants": variants,
                        }

                    else:

                        print(
                            ""
                            "      "
                            "[FEHLER] "
                            "Kein gültiger "
                            "Stream gefunden."
                        )

                        write_error(
                            cid,
                            channel,
                        )

                        results[cid] = None

                except Exception as e:

                    print(
                        "[KANAL FEHLER] "
                        f"{str(e)[:250]}"
                    )

                    write_error(
                        cid,
                        channel,
                    )

                    results[cid] = None

                finally:

                    try:
                        page.close()
                    except Exception:
                        pass

                elapsed = (
                    time.monotonic()
                    - sender_start
                )

                print(
                    f"[ZEIT] "
                    f"{channel['name']}: "
                    f"{elapsed:.1f} Sekunden"
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

    # ============================================================
    # DATEIEN SCHREIBEN
    # ============================================================

    write_all_m3u(
        results
    )

    total_time = (
        time.monotonic()
        - start
    )

    print("")
    print("=" * 65)
    print(
        "SCAN ABGESCHLOSSEN"
    )
    print("=" * 65)

    print(
        f"Gesamtzeit: "
        f"{total_time:.1f} Sekunden"
    )

    erfolgreich = sum(
        1
        for value in results.values()
        if value
        and value.get("master")
    )

    print(
        f"Erfolgreich: "
        f"{erfolgreich}/"
        f"{len(CHANNELS)}"
    )

    print(
        f"Playlist: "
        f"{PLAYLIST_FILE}"
    )

    print("=" * 65)


if __name__ == "__main__":
    main()
