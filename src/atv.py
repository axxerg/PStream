import json
import re
import time
import random
import requests
from pathlib import Path
from urllib.parse import quote


PAGE_URL = "https://www.atv.com.tr/canli-yayin"
OUTPUT_FILE = Path("output/atv.m3u8")

WEBSITE_ID = "0fe2a405-8afa-4238-b429-e5f96aec3a5c"
VIDEO_ID = "00000000-0000-0000-0000-000000000000"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0.0.0 Safari/537.36"
)


def recursive_find(obj, wanted):
    """Sucht einen Wert rekursiv im JSON."""

    if isinstance(obj, dict):
        for key, value in obj.items():

            if key.lower() == wanted.lower():
                return value

            result = recursive_find(value, wanted)

            if result is not None:
                return result

    elif isinstance(obj, list):
        for item in obj:
            result = recursive_find(item, wanted)

            if result is not None:
                return result

    return None


def find_tmd_script(html):
    """Findet tmdplayersetupv2.js."""

    match = re.search(
        r'https?://[^"\']*tmdplayersetupv2\.js[^"\']*',
        html,
        re.IGNORECASE
    )

    if match:
        return match.group(0).replace("\\/", "/")

    return (
        "https://i.tmgrup.com.tr/"
        "videojs/js/tmdplayersetupv2.js?v=926"
    )


def find_base_url(js):
    """Findet baseRequestUrl."""

    patterns = [
        r'baseRequestUrl\s*:\s*["\']([^"\']+)',
        r'baseRequestUrl\s*=\s*["\']([^"\']+)',
        r'"baseRequestUrl"\s*:\s*"([^"]+)',
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            js,
            re.IGNORECASE
        )

        if match:
            return match.group(1)

    return None


def get_tmd_data(session, base_url):

    url = (
        base_url.rstrip("/")
        + "/getvideo/"
        + WEBSITE_ID
        + "/"
        + VIDEO_ID
    )

    print("TMD API:")
    print(url)

    response = session.get(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "X-isApp": "false",
            "Content-Type": "application/json",
            "Referer": PAGE_URL,
            "Origin": "https://www.atv.com.tr",
        },
        timeout=30
    )

    print("TMD HTTP:", response.status_code)

    response.raise_for_status()

    return response.json()


def get_secure_url(session, stream_url):

    random_number = random.randint(
        1,
        1000000
    )

    url = (
        "https://securevideotoken.tmgrup.com.tr/"
        "webtv/secure?"
        + str(random_number)
        + "&url="
        + quote(stream_url, safe="")
    )

    print("Secure Token Request:")
    print(url)

    response = session.get(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "X-isApp": "false",
            "X-Rand": str(
                int(time.time() * 1000)
            ),
            "Referer": PAGE_URL,
            "Origin": "https://www.atv.com.tr",
            "Accept": "application/json,text/plain,*/*",
        },
        timeout=30
    )

    print(
        "Secure Token HTTP:",
        response.status_code
    )

    response.raise_for_status()

    data = response.json()

    # Normal response
    if isinstance(data, dict):

        if data.get("Url"):
            return data["Url"]

        if data.get("url"):
            return data["url"]

    # Verschachtelte Response
    for key in (
        "data",
        "video",
        "videoUrls"
    ):

        value = data.get(key)

        if isinstance(value, dict):

            if value.get("Url"):
                return value["Url"]

            if value.get("url"):
                return value["url"]

    raise RuntimeError(
        "Secure Token liefert keine Stream-URL."
    )


def main():

    session = requests.Session()

    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    })

    # ========================================================
    # 1. ATV-Seite
    # ========================================================

    print("Lade ATV-Seite...")

    page = session.get(
        PAGE_URL,
        timeout=30
    )

    page.raise_for_status()

    html = page.text

    print("ATV-Seite geladen.")

    # ========================================================
    # 2. TMD Player
    # ========================================================

    tmd_script = find_tmd_script(html)

    print()
    print("TMD Player:")
    print(tmd_script)

    js_response = session.get(
        tmd_script,
        timeout=30
    )

    js_response.raise_for_status()

    js = js_response.text

    # ========================================================
    # 3. baseRequestUrl
    # ========================================================

    base_url = find_base_url(js)

    if not base_url:

        Path("output").mkdir(
            parents=True,
            exist_ok=True
        )

        Path(
            "output/tmdplayersetupv2.js"
        ).write_text(
            js,
            encoding="utf-8"
        )

        raise RuntimeError(
            "baseRequestUrl nicht gefunden."
        )

    print()
    print("baseRequestUrl:")
    print(base_url)

    # ========================================================
    # 4. TMD API
    # ========================================================

    data = get_tmd_data(
        session,
        base_url
    )

    # Debug speichern
    Path("output").mkdir(
        parents=True,
        exist_ok=True
    )

    Path(
        "output/tmd.json"
    ).write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    # ========================================================
    # 5. isAtvEU überall suchen
    # ========================================================

    is_europe = recursive_find(
        data,
        "isAtvEU"
    )

    if is_europe is None:
        is_europe = recursive_find(
            data,
            "IsAtvEU"
        )

    print()
    print("isAtvEU:", is_europe)

    # ========================================================
    # 6. ATV EUROPA erzwingen
    # ========================================================

    # Wir wollen ausdrücklich ATV Europa.
    #
    # Die Seite liefert den Europa-Stream:
    #
    # trkvz-live.ercdn.net/atvavrupa/
    #
    # Die nackte URL darf NICHT direkt aufgerufen werden.
    # Sie wird anschließend über securevideotoken signiert.

    stream_base = (
        "https://trkvz-live.ercdn.net/"
        "atvavrupa/"
        "atvavrupa_576p.m3u8"
    )

    print()
    print("ATV Avrupa Basis:")
    print(stream_base)

    # ========================================================
    # 7. Secure Token
    # ========================================================

    stream_url = get_secure_url(
        session,
        stream_base
    )

    print()
    print("Signierte URL:")
    print(stream_url)

    # ========================================================
    # 8. Prüfen
    # ========================================================

    if (
        "trkvz-live.ercdn.net/atvavrupa/"
        not in stream_url.lower()
    ):
        raise RuntimeError(
            "Secure Token hat keine ATV-Avrupa-URL geliefert:\n"
            + stream_url
        )

    if ".m3u8" not in stream_url.lower():
        raise RuntimeError(
            "Keine M3U8-URL erhalten:\n"
            + stream_url
        )

    # ========================================================
    # 9. M3U8 schreiben
    # ========================================================

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT_FILE.write_text(
        "#EXTM3U\n"
        "#EXTINF:-1,ATV Avrupa\n"
        + stream_url
        + "\n",
        encoding="utf-8"
    )

    print()
    print("====================================")
    print("ATV EUROPA ERFOLGREICH")
    print("====================================")
    print(stream_url)
    print()
    print("Gespeichert:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()
