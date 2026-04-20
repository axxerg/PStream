import re
import requests
import os

OUTPUT_FILE = "output/showturk.m3u8"

URL = "https://www.showturk.com.tr/canli-yayin"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.showturk.com.tr/"
}

def find_m3u8(text):
    match = re.search(r"https?://[^\"'\\s]+\\.m3u8[^\"'\\s]*", text)
    return match.group(0) if match else None


def main():
    print("Fetching page...")
    res = requests.get(URL, headers=HEADERS, timeout=10)
    html = res.text

    m3u8 = find_m3u8(html)

    if not m3u8:
        print("❌ No m3u8 found")
        return

    print("✅ Found stream:", m3u8)

    os.makedirs("output", exist_ok=True)

    with open(OUTPUT_FILE, "w") as f:
        f.write(m3u8)

    print("💾 Saved to", OUTPUT_FILE)


if __name__ == "__main__":
    main()
