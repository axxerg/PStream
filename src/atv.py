import re
import json
import time
import random
import requests
from pathlib import Path
from urllib.parse import quote


PAGE_URL = "https://www.atv.com.tr/canli-yayin"
OUTPUT_FILE = Path("output/atv.m3u8")

WEBSITE_ID = "0fe2a405-8afa-4238-b429-e5f96aec3a5c"
VIDEO_ID = "00000000-0000-0000-0000-000000000000"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
}


def find_player_script(html):
    """
    Findet tmdplayersetupv2.js auf der ATV-Seite.
    """

    match = re.search(
        r'https?://[^"\']*tmdplayersetupv2\.js[^"\']*',
        html,
        re.IGNORECASE,
    )

    if match:
        return match.group(0).replace("\\/", "/")

    # Relative Variante
    match = re.search(
        r'(?:src=["\'])([^"\']*tmdplayersetupv2\.js[^"\']*)',
        html,
        re.IGNORECASE,
    )

    if match:
        url = match.group(1)

        if url.startswith("//"):
            return "https:" + url

        if url.startswith("/"):
            return "https://www.atv.com.tr" + url

        return url

    return None


def find_base_request_url(js):
    """
    Versucht baseRequestUrl aus der TMD-JS-Datei zu extrahieren.
    """

    patterns = [
        r'baseRequestUrl\s*:\s*["\']([^"\']+)["\']',
        r'baseRequestUrl\s*=\s*["\']([^"\']+)["\']',
        r'"baseRequestUrl"\s*:\s*"([^"]+)"',
        r"'baseRequestUrl'\s*:\s*'([^']+)'",
    ]

    for pattern in patterns:
        match = re.search(pattern, js)

        if match:
            return match.group(1)

    return None


def get_tmd_data(session, base_url):
    """
    Ruft den TMD getvideo Endpoint auf.
    """

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
            "X-isApp": "false",
            "Content-Type": "application/json",
        },
        timeout=30,
    )

    print("TMD HTTP:", response.status_code)

    response.raise_for_status()

    data = response.json()

    if not data.get("success"):
        raise RuntimeError(
            "TMD API meldet success=false"
        )

    return data


def build_atv_avrupa_url(video):
    """
    ATV Avrupa URL entsprechend PlayerDaion.
    """

    is_europe = video.get("isAtvEU")

    print("isAtvEU:", is_europe)

    if not is_europe:
        raise RuntimeError(
            "TMD meldet isAtvEU=false. "
            "Damit würde der normale ATV-Stream verwendet werden."
        )

    # Der europäische Basisstream aus PlayerDaion.
    return (
        "https://trkvz-live.ercdn.net/"
        "atvavrupa/"
        "atvavrupa_576p.m3u8"
    )


def secure_token(session, video_url):
    """
    Reproduziert RequestSecureToken().
    """

    random_number = random.randint(1, 1_000_000)

    url = (
        "https://securevideotoken.tmgrup.com.tr/"
        "webtv/secure?"
        + str(random_number)
        + "&url="
        + quote(video_url, safe="")
    )

    headers = {
        "X-isApp": "false",
        "X-Rand": str(int(time.time() * 1000)),
        "User-Agent": HEADERS["User-Agent"],
        "Referer": PAGE_URL,
        "Origin": "https://www.atv.com.tr",
    }

    print()
    print("Secure Token Request:")
    print(url)

    response = session.get(
        url,
        headers=headers,
        timeout=30,
    )

    print("Token HTTP:", response.status_code)

    response.raise_for_status()

    data = response.json()

    print("Token Response erhalten.")

    # TMD verwendet videoUrls.Url
    if isinstance(data, dict):
        if data.get("Url"):
            return data["Url"]

        if data.get("url"):
            return data["url"]

        # Falls die Antwort verschachtelt ist
        for key in ("data", "video", "videoUrls"):
            obj = data.get(key)

            if isinstance(obj, dict):
                if obj.get("Url"):
                    return obj["Url"]

                if obj.get("url"):
                    return obj["url"]

    raise RuntimeError(
        "Secure-Token-Antwort enthält keine Url."
    )


def main():

    session = requests.Session()
    session.headers.update(HEADERS)

    # --------------------------------------------------
    # 1. ATV Seite
    # --------------------------------------------------

    print("Lade ATV-Seite...")

    page_response = session.get(
        PAGE_URL,
        timeout=30,
    )

    page_response.raise_for_status()

    html = page_response.text

    print("ATV-Seite geladen.")

    # --------------------------------------------------
    # 2. TMD JS
    # --------------------------------------------------

    player_script = find_player_script(html)

    if not player_script:
        raise RuntimeError(
            "tmdplayersetupv2.js wurde nicht gefunden."
        )

    print()
    print("TMD Player:")
    print(player_script)

    js_response = session.get(
        player_script,
        timeout=30,
    )

    js_response.raise_for_status()

    js = js_response.text

    # --------------------------------------------------
    # 3. baseRequestUrl
    # --------------------------------------------------

    base_url = find_base_request_url(js)

    if not base_url:

        Path("output").mkdir(
            parents=True,
            exist_ok=True,
        )

        Path("output/tmdplayersetupv2.js").write_text(
            js,
            encoding="utf-8",
        )

        raise RuntimeError(
            "baseRequestUrl konnte nicht gefunden werden. "
            "Die heruntergeladene JS-Datei liegt unter "
            "output/tmdplayersetupv2.js"
        )

    print()
    print("baseRequestUrl:")
    print(base_url)

    # --------------------------------------------------
    # 4. TMD getvideo
    # --------------------------------------------------

    data = get_tmd_data(
        session,
        base_url,
    )

    # Debug speichern
    Path("output").mkdir(
        parents=True,
        exist_ok=True,
    )

    Path("output/tmd.json").write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    video = data.get("video")

    if not isinstance(video, dict):
        raise RuntimeError(
            "TMD-Antwort enthält kein video-Objekt."
        )

    # --------------------------------------------------
    # 5. ATV Europa URL
    # --------------------------------------------------

    video_url = build_atv_avrupa_url(video)

    print()
    print("ATV Europa Basis-URL:")
    print(video_url)

    # --------------------------------------------------
    # 6. Secure Token
    # --------------------------------------------------

    is_ztk = video.get("IsZtkTokenActive")

    print("IsZtkTokenActive:", is_ztk)

    if is_ztk:
        stream_url = secure_token(
            session,
            video_url,
        )
    else:
        stream_url = video_url

    # --------------------------------------------------
    # 7. Kontrolle
    # --------------------------------------------------

    if "trkvz-live.ercdn.net/atvavrupa/" not in stream_url:
        raise RuntimeError(
            "Die erhaltene URL ist NICHT ATV Avrupa:\n"
            + stream_url
        )

    if ".m3u8" not in stream_url:
        raise RuntimeError(
            "Die erhaltene URL ist keine M3U8:\n"
            + stream_url
        )

    print()
    print("======================================")
    print("ATV EUROPA STREAM")
    print("======================================")
    print(stream_url)

    # --------------------------------------------------
    # 8. M3U schreiben
    # --------------------------------------------------

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_FILE.write_text(
        "#EXTM3U\n"
        "#EXTINF:-1,ATV Avrupa\n"
        + stream_url
        + "\n",
        encoding="utf-8",
    )

    print()
    print("Gespeichert:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()
