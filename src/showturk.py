import re
import requests
import os
from urllib.parse import urljoin

URL = "https://www.showturk.com.tr/canli-yayin"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.showturk.com.tr/"
}

OUTPUT = "output/showturk.m3u8"


def fetch(url):
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        res.raise_for_status()
        return res.text
    except Exception as e:
        print(f"❌ Request failed: {url}")
        print(e)
        return ""


def extract_m3u8(text):
    return re.findall(r"https?://[^\"'\\s]+\\.m3u8[^\"'\\s]*", text)


def extract_iframes(html):
    return re.findall(r'<iframe[^>]+src=["\']([^"\']+)["\']', html)


def is_valid_iframe(url):
    bad = [
        "googletagmanager",
        "doubleclick",
        "ads",
        "analytics"
    ]
    return not any(b in url for b in bad)


def save(url):
    os.makedirs("output", exist_ok=True)
    with open(OUTPUT, "w") as f:
        f.write(url)
    print("💾 Saved:", OUTPUT)


def main():
    print("=== ShowTurk Extractor ===")

    # 1️⃣ Hauptseite
    print("➡️ Load main page")
    html = fetch(URL)

    # 2️⃣ Direkt nach m3u8 suchen
    m3u8_list = extract_m3u8(html)
    if m3u8_list:
        print("✅ Found direct stream")
        print(m3u8_list[0])
        save(m3u8_list[0])
        return

    print("⚠️ No direct stream, checking iframes...")

    # 3️⃣ Alle iframes prüfen
    iframes = extract_iframes(html)

    for iframe in iframes:
        iframe_url = urljoin(URL, iframe)

        if not is_valid_iframe(iframe_url):
            print("⏭️ Skip iframe:", iframe_url)
            continue

        print("➡️ Checking iframe:", iframe_url)

        html2 = fetch(iframe_url)

        m3u8_list = extract_m3u8(html2)
        if m3u8_list:
            print("✅ Found stream in iframe")
            print(m3u8_list[0])
            save(m3u8_list[0])
            return

    # 4️⃣ Fallback bekannte CDN (optional)
    print("⚠️ Trying fallback CDN...")

    fallback = "https://ciner-live.ercdn.net/showturk/playlist.m3u8"

    try:
        r = requests.head(fallback, timeout=5)
        if r.status_code == 200:
            print("✅ Fallback works")
            save(fallback)
            return
        else:
            print("❌ Fallback failed:", r.status_code)
    except:
        print("❌ Fallback unreachable")

    print("❌ No stream found at all")


if __name__ == "__main__":
    main()
