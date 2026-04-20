import re
import requests
from urllib.parse import urljoin
import os

URL = "https://www.showturk.com.tr/canli-yayin"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.showturk.com.tr/"
}

OUTPUT = "output/showturk.m3u8"

re_m3u8 = re.compile(r"https?://[^\"'\\s]+\\.m3u8[^\"'\\s]*")
re_iframe = re.compile(r'<iframe[^>]+src=["\']([^"\']+)["\']')


def fetch(url):
    return requests.get(url, headers=HEADERS, timeout=10).text


def find_m3u8(text):
    m = re_m3u8.search(text)
    return m.group(0) if m else None


def find_iframe(html):
    m = re_iframe.search(html)
    return m.group(1) if m else None


def main():
    print("Step 1: load main page")
    html = fetch(URL)

    # 1️⃣ direkt suchen
    m3u8 = find_m3u8(html)
    if m3u8:
        print("✅ Found direct stream")
        save(m3u8)
        return

    # 2️⃣ iframe prüfen
    iframe = find_iframe(html)
    if iframe:
        iframe_url = urljoin(URL, iframe)
        print("Step 2: load iframe:", iframe_url)

        html2 = fetch(iframe_url)

        m3u8 = find_m3u8(html2)
        if m3u8:
            print("✅ Found stream in iframe")
            save(m3u8)
            return

    print("❌ No stream found")


def save(url):
    os.makedirs("output", exist_ok=True)
    with open(OUTPUT, "w") as f:
        f.write(url)
    print("💾 Saved:", OUTPUT)


if __name__ == "__main__":
    main()
