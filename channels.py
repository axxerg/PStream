import os
import re
import time
import base64
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
    "cnnturk": {
        "name": "CNN TURK",
        "url": "https://www.cnnturk.com/canli-yayin",
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

    # CNN TURK bewusst ohne erfundenen Fallback.
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
    "tv8": "https://www.tv8.com.tr/",
    "tv8int": "https://www.tv8.com.tr/",
    "kanald": "https://www.kanald.com.tr/",
    "eurod": "https://www.eurod.com.tr/",
    "teve2": "https://www.teve2.com.tr/",
    "startv": "https://www.startv.com.tr/",
    "eurostar": "https://www.eurostartv.com.tr/",
    "cnnturk": "https://www.cnnturk.com/",
}


# ============================================================
# SENDER MIT TIEFENSCAN
# ============================================================

DEEP_SCAN_CHANNELS = {
    "cnnturk",
    "eurod",
    "tv8int",
}


# ============================================================
# SENDER-SPEZIFISCHE STREAM-PRÜFUNG
# ============================================================

def is_channel_stream(channel_id, url):
    """
    Verhindert, dass eine Webseite den Stream eines anderen
    Senders liefert.

    Besonders wichtig bei CNN TURK, weil die Seite teilweise
    auch Eurostar-Streams lädt.
    """

    url = url.lower()

    # --------------------------------------------------------
    # CNN TURK
    # --------------------------------------------------------

    if channel_id == "cnnturk":
        return (
            "live.duhnet.tv" in url
            and "cnnturknp" in url
        )

    # --------------------------------------------------------
    # EURO D
    # --------------------------------------------------------

    if channel_id == "eurod":
        return (
            "eurod-live.daioncdn.net" in url
            or "eurod" in url
        )

    # --------------------------------------------------------
    # TV8 INTERNATIONAL
    # --------------------------------------------------------

    if channel_id == "tv8int":
        return (
            "tv8.daioncdn.net" in url
            and "tv8" in url
        )

    # --------------------------------------------------------
    # SHOW TV
    # --------------------------------------------------------

    if channel_id == "showtv":
        return (
            "ciner-live.ercdn.net/showtv" in url
            or "showtv" in url
        )

    # --------------------------------------------------------
    # SHOWTURK
    # --------------------------------------------------------

    if channel_id == "showturk":
        return (
            "ciner-live.ercdn.net/showturk" in url
            or "showturk" in url
        )

    # --------------------------------------------------------
    # SHOWMAX
    # --------------------------------------------------------

    if channel_id == "showmax":
        return (
            "ciner-live.ercdn.net/showmax" in url
            or "showmax" in url
        )

    # --------------------------------------------------------
    # NOW TV
    # --------------------------------------------------------

    if channel_id == "nowtv":
        return (
            "ciner-live.ercdn.net/nowtv" in url
            or "nowtv" in url
        )

    # --------------------------------------------------------
    # TV8
    # --------------------------------------------------------

    if channel_id == "tv8":
        return (
            "tv8.daioncdn.net" in url
        )

    # --------------------------------------------------------
    # KANAL D
    # --------------------------------------------------------

    if channel_id == "kanald":
        return (
            "kanald-live.daioncdn.net" in url
            or "kanald" in url
        )

    # --------------------------------------------------------
    # TEVE2
    # --------------------------------------------------------

    if channel_id == "teve2":
        return (
            "teve2-live.daioncdn.net" in url
            or "teve2" in url
        )

    # --------------------------------------------------------
    # STAR TV
    # --------------------------------------------------------

    if channel_id == "startv":
        return (
            "dogus-live.daioncdn.net/startv" in url
            or "gt-startv" in url
            or "startv" in url
        )

    # --------------------------------------------------------
    # EUROSTAR
    # --------------------------------------------------------

    if channel_id == "eurostar":
        return (
            "gt-eurostar" in url
            or "eurostar" in url
        )

    return True


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


def score_stream(url):

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

    if "playlist.m3u8" in lower:
        score += 20

    if "master" in lower:
        score += 15

    if "index.m3u8" in lower:
        score += 10

    if "securevideotoken" in lower:
        score -= 100

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
# MASTER PLAYLIST
# ============================================================

def parse_master_playlist(
    master_url,
    text,
):

    variants = []

    if not text:
        return variants

    if "#EXT-X-STREAM-INF" not in text:
        return variants

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    for index, line in enumerate(lines):

        if not line.startswith(
            "#EXT-X-STREAM-INF"
        ):
            continue

        if index + 1 >= len(lines):
            continue

        next_line = lines[index + 1]

        if next_line.startswith("#"):
            continue

        variant = next_line

        if variant.startswith("//"):
            variant = "https:" + variant

        elif variant.startswith("/"):
            parsed = urlparse(
                master_url
            )

            variant = (
                f"{parsed.scheme}://"
                f"{parsed.netloc}"
                f"{variant}"
            )

        elif not variant.startswith("http"):

            base = master_url.rsplit(
                "/",
                1,
            )[0]

            variant = (
                f"{base}/{variant}"
            )

        variant = normalize_url(
            variant
        )

        if is_valid_m3u8_url(
            variant
        ):
            variants.append(
                variant
            )

    return variants


def collect_all_variants(url):

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )
    }

    try:

        response = requests.get(
            url,
            headers=headers,
            timeout=5,
        )

        if response.status_code != 200:
            return [url]

        variants = parse_master_playlist(
            url,
            response.text,
        )

        if variants:

            unique = []

            for variant in variants:

                if variant not in unique:
                    unique.append(
                        variant
                    )

            return unique

    except Exception:
        pass

    return [url]


# ============================================================
# ATV
# ============================================================

def extract_atv_m3u8_from_secure(url):

    candidates = []

    try:

        parsed = urlparse(url)

        params = parse_qs(
            parsed.query
        )

        for key in (
            "url",
            "url2",
        ):

            values = params.get(
                key,
                [],
            )

            for value in values:

                value = unquote(
                    value
                )

                value = normalize_url(
                    value
                )

                if (
                    "trkvz-live.ercdn.net"
                    in value
                ):

                    candidates.extend(
                        extract_m3u8(
                            value
                        )
                    )

                    if ".m3u8" in value.lower():
                        candidates.append(
                            value
                        )

    except Exception:
        pass

    for value in extract_m3u8(url):

        if (
            "trkvz-live.ercdn.net"
            in value
        ):
            candidates.append(
                value
            )

    result = []

    for candidate in candidates:

        candidate = normalize_url(
            candidate
        )

        if (
            "trkvz-live.ercdn.net"
            in candidate
            and is_valid_m3u8_url(
                candidate
            )
            and candidate not in result
        ):

            result.append(
                candidate
            )

    return result


def resolve_atv_stream(url):

    if not url:
        return []

    lower = url.lower()

    if (
        "securevideotoken.tmgrup.com.tr"
        not in lower
    ):

        if (
            "trkvz-live.ercdn.net"
            in lower
        ):
            return [url]

        return []

    direct_candidates = (
        extract_atv_m3u8_from_secure(
            url
        )
    )

    result = []

    for candidate in direct_candidates:

        variants = collect_all_variants(
            candidate
        )

        for variant in variants:

            if (
                "trkvz-live.ercdn.net"
                in variant
                and is_valid_m3u8_url(
                    variant
                )
                and variant not in result
            ):

                result.append(
                    variant
                )

    result.sort(
        key=lambda x: (
            0
            if quality_from_url(x) == 576
            else 1,
            -score_stream(x),
        )
    )

    return result


# ============================================================
# TIEFER SEITENSCAN
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

                candidates.append(
                    url
                )

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
            add_urls(resource)

    except Exception:
        pass

    # --------------------------------------------------------
    # HTML
    # --------------------------------------------------------

    try:

        source = page.content()

        add_urls(source)

        add_urls(
            unquote(source)
        )

    except Exception:
        pass

    # --------------------------------------------------------
    # Scripts
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
    # Data-Attribute
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

    # --------------------------------------------------------
    # IFrames
    # --------------------------------------------------------

    try:

        iframe_elements = page.locator(
            "iframe"
        ).all()

        for iframe in iframe_elements:

            iframe_page = None

            try:

                src = iframe.get_attribute(
                    "src"
                )

                if not src:
                    continue

                src = normalize_url(
                    src
                )

                if ".m3u8" in src.lower():

                    add_urls(src)

                    continue

                try:

                    iframe_page = (
                        page.context.new_page()
                    )

                    iframe_page.goto(
                        src,
                        wait_until=(
                            "domcontentloaded"
                        ),
                        timeout=8000,
                    )

                    iframe_page.wait_for_timeout(
                        1500
                    )

                    add_urls(
                        iframe_page.content()
                    )

                    resources = iframe_page.evaluate(
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

                finally:

                    if iframe_page:

                        try:
                            iframe_page.close()
                        except Exception:
                            pass

            except Exception:
                pass

    except Exception:
        pass

    # --------------------------------------------------------
    # Frames
    # --------------------------------------------------------

    try:

        for frame in page.frames:

            try:

                add_urls(
                    frame.content()
                )

            except Exception:
                pass

            try:

                frame_scripts = frame.locator(
                    "script"
                ).all()

                for script in frame_scripts:

                    try:

                        add_urls(
                            script.text_content()
                        )

                    except Exception:
                        pass

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

    deep_scan = (
        channel_id
        in DEEP_SCAN_CHANNELS
    )

    max_wait = (
        14
        if deep_scan
        else 7
    )

    gefunden = False

    def add_candidate(url):

        nonlocal candidates

        url = normalize_url(
            url
        )

        if not url:
            return

        # ----------------------------------------------------
        # ATV Secure-URL niemals speichern
        # ----------------------------------------------------

        if (
            channel_id == "atv"
            and
            "securevideotoken.tmgrup.com.tr"
            in url.lower()
        ):

            resolved = (
                resolve_atv_stream(
                    url
                )
            )

            for item in resolved:

                if item not in candidates:
                    candidates.append(
                        item
                    )

            return

        if not is_valid_m3u8_url(
            url
        ):
            return

        # ----------------------------------------------------
        # SENDER-FILTER
        # ----------------------------------------------------

        if not is_channel_stream(
            channel_id,
            url,
        ):

            print(
                f"  Falscher Sender-Stream "
                f"ignoriert: {url}"
            )

            return

        if url not in candidates:

            candidates.append(
                url
            )

    def capture_response(
        response
    ):

        nonlocal gefunden

        try:

            url = normalize_url(
                response.url
            )

            if ".m3u8" not in url.lower():
                return

            if deep_scan:

                add_candidate(
                    url
                )

                return

            add_candidate(
                url
            )

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

        page.wait_for_timeout(
            1500
        )

        start = time.monotonic()

        while (
            time.monotonic() - start
            < max_wait
        ):

            if (
                gefunden
                and not deep_scan
            ):
                break

            page.wait_for_timeout(
                500
            )

        # ----------------------------------------------------
        # Tiefer Scan
        # ----------------------------------------------------

        if (
            deep_scan
            or not candidates
        ):

            print(
                "  Tiefer Seitenscan..."
            )

            for url in scan_page(
                page
            ):

                add_candidate(
                    url
                )

    except Exception as exc:

        print(
            f"  Browser-Fehler: {exc}"
        )

        try:

            for url in scan_page(
                page
            ):

                add_candidate(
                    url
                )

        except Exception:
            pass

    # --------------------------------------------------------
    # ATV
    # --------------------------------------------------------

    if channel_id == "atv":

        resolved = []

        for candidate in candidates:

            if (
                "securevideotoken.tmgrup.com.tr"
                in candidate.lower()
            ):

                for item in resolve_atv_stream(
                    candidate
                ):

                    if item not in resolved:
                        resolved.append(
                            item
                        )

            elif (
                "trkvz-live.ercdn.net"
                in candidate.lower()
            ):

                if candidate not in resolved:
                    resolved.append(
                        candidate
                    )

        candidates = resolved

        candidates.sort(
            key=lambda x: (
                0
                if quality_from_url(x) == 576
                else 1,
                -score_stream(x),
            )
        )

    else:

        candidates.sort(
            key=score_stream,
            reverse=True,
        )

    # --------------------------------------------------------
    # Validieren
    # --------------------------------------------------------

    referer = REFERERS.get(
        channel_id
    )

    valid = []

    for candidate in candidates:

        if not is_valid_m3u8_url(
            candidate
        ):
            continue

        # Sicherheitshalber erneut
        # Sender prüfen.
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

            valid.append(
                candidate
            )

            if not deep_scan:
                break

    return valid


# ============================================================
# FALLBACK
# ============================================================

def fallback_find(
    channel_id
):

    candidates = FALLBACK_STREAMS.get(
        channel_id,
        [],
    )

    valid = []

    for url in candidates:

        if not is_valid_m3u8_url(
            url
        ):
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
            referer=REFERERS.get(
                channel_id
            ),
            timeout=5,
        ):

            valid.append(
                url
            )

    return valid


# ============================================================
# M3U DATEIEN
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

    lines = [
        "#EXTM3U"
    ]

    for stream in streams:

        lines.append(
            f'#EXTINF:-1 tvg-id="{channel_id}" '
            f'tvg-name="{channel["name"]}",'
            f'{channel["name"]}'
        )

        lines.append(
            stream
        )

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as file:

        file.write(
            "\n".join(lines)
            + "\n"
        )


def write_all_variants(
    channel_id,
    channel,
    streams,
):

    path = os.path.join(
        STREAMS_DIR,
        f"{channel_id}_all.m3u8",
    )

    lines = [
        "#EXTM3U"
    ]

    for stream in streams:

        lines.append(
            f'#EXTINF:-1 tvg-id="{channel_id}" '
            f'tvg-name="{channel["name"]}",'
            f'{channel["name"]}'
        )

        lines.append(
            stream
        )

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as file:

        file.write(
            "\n".join(lines)
            + "\n"
        )


def write_all_m3u(
    results
):

    path = os.path.join(
        STREAMS_DIR,
        "all.m3u",
    )

    lines = [
        "#EXTM3U"
    ]

    for channel_id, data in results.items():

        channel = CHANNELS[
            channel_id
        ]

        for stream in data:

            lines.append(
                f'#EXTINF:-1 tvg-id="{channel_id}" '
                f'tvg-name="{channel["name"]}",'
                f'{channel["name"]}'
            )

            lines.append(
                stream
            )

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as file:

        file.write(
            "\n".join(lines)
            + "\n"
        )


def write_links(
    results
):

    path = os.path.join(
        STREAMS_DIR,
        "links.txt",
    )

    lines = []

    for channel_id, streams in results.items():

        channel = CHANNELS[
            channel_id
        ]

        lines.append(
            f"### {channel['name']}"
        )

        for stream in streams:
            lines.append(
                stream
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
# PLAYLIST MATCHING
# ============================================================

def playlist_channel_matches(
    extinf_line,
    channel_id,
):

    text = extinf_line.lower()

    if channel_id == "showtv":
        return (
            "show tv" in text
            or 'tvg-id="showtv' in text
        )

    if channel_id == "showturk":
        return (
            "showturk" in text
            or "show türk" in text
        )

    if channel_id == "showmax":
        return (
            "showmax" in text
        )

    if channel_id == "nowtv":
        return (
            "now tv" in text
            or "nowtv" in text
        )

    if channel_id == "atv":
        return (
            'tvg-id="atv' in text
            or ",atv" in text
        )

    if channel_id == "tv8":
        return (
            'tvg-id="tv8' in text
            and "international" not in text
        )

    if channel_id == "tv8int":
        return (
            "tv8 international" in text
            or "tv8int" in text
        )

    if channel_id == "kanald":
        return (
            "kanal d" in text
            or "kanald" in text
        )

    if channel_id == "eurod":
        return (
            "euro d" in text
            or "eurod" in text
        )

    if channel_id == "teve2":
        return (
            "teve2" in text
        )

    if channel_id == "startv":
        return (
            "star tv" in text
            or "startv" in text
        )

    if channel_id == "eurostar":
        return (
            "eurostar" in text
            or "euro star" in text
        )

    if channel_id == "cnnturk":
        return (
            'tvg-id="cnn türk hd.tr"' in text
            or "cnn turk" in text
            or "cnn türk" in text
            or "cnn türk hd" in text
        )

    return False


# ============================================================
# HAUPT-PLAYLIST AKTUALISIEREN
# ============================================================

def update_existing_playlist(
    results
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

    for channel_id, streams in results.items():

        if not streams:
            continue

        replacement = streams[0]

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
                channel_id,
            ):
                continue

            found_channel = True

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
                    replacement
                    + "\n"
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

        file.writelines(
            lines
        )


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
            f"Kanal: "
            f"{CHANNELS[channel_id]['name']}\n"
        )

        file.write(
            f"URL: "
            f"{CHANNELS[channel_id]['url']}\n"
        )

        file.write(
            f"Status: {message}\n"
        )


def remove_error(
    channel_id
):

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

    print(
        "=" * 70
    )

    print(
        "IPTV SENDER-SCANNER"
    )

    print(
        "=" * 70
    )

    print(
        f"Playlist: {PLAYLIST_FILE}"
    )

    print(
        f"Sender: {len(CHANNELS)}"
    )

    print(
        "=" * 70
    )

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
        # Sender scannen
        # ----------------------------------------------------

        for channel_id, channel in CHANNELS.items():

            print()
            print(
                "-" * 70
            )

            print(
                f"Kanal: {channel['name']}"
            )

            print(
                f"URL: {channel['url']}"
            )

            print(
                "-" * 70
            )

            streams = []

            # ------------------------------------------------
            # Offizielle Webseite
            # ------------------------------------------------

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
            # Fallback
            # ------------------------------------------------

            if not streams:

                print(
                    "  Kein Stream über die Webseite gefunden."
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
            # Ergebnis
            # ------------------------------------------------

            if streams:

                unique = []

                for stream in streams:

                    if stream not in unique:
                        unique.append(
                            stream
                        )

                streams = unique

                results[
                    channel_id
                ] = streams

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

                write_all_variants(
                    channel_id,
                    channel,
                    streams,
                )

                remove_error(
                    channel_id
                )

            else:

                results[
                    channel_id
                ] = []

                print()

                print(
                    "  FEHLER: M3U8 nicht gefunden"
                )

                write_error(
                    channel_id,
                    "M3U8 nicht gefunden",
                )

        # ----------------------------------------------------
        # Browser schließen
        # ----------------------------------------------------

        context.close()

        browser.close()

    # ========================================================
    # GESAMTDATEIEN
    # ========================================================

    write_all_m3u(
        results
    )

    write_links(
        results
    )

    # ========================================================
    # HAUPT-PLAYLIST
    # ========================================================

    print()

    print(
        "=" * 70
    )

    print(
        "HAUPT-PLAYLIST AKTUALISIEREN"
    )

    print(
        "=" * 70
    )

    update_existing_playlist(
        results
    )

    # ========================================================
    # ABSCHLUSS
    # ========================================================

    erfolgreich = sum(
        1
        for streams in results.values()
        if streams
    )

    fehler = (
        len(CHANNELS)
        - erfolgreich
    )

    print()

    print(
        "=" * 70
    )

    print(
        "SCAN ABGESCHLOSSEN"
    )

    print(
        "=" * 70
    )

    print(
        f"Erfolgreich: "
        f"{erfolgreich}/{len(CHANNELS)}"
    )

    print(
        f"Fehler:      "
        f"{fehler}/{len(CHANNELS)}"
    )

    print()

    print(
        f"Playlist: "
        f"{PLAYLIST_FILE}"
    )

    print(
        f"Streams:  "
        f"{STREAMS_DIR}/"
    )

    print(
        "=" * 70
    )


if __name__ == "__main__":
    main()
