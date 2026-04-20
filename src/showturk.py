import requests
import os

OUTPUT = "output/showturk.m3u8"

def main():
    print("=== ShowTurk Extractor ===")

    os.makedirs("output", exist_ok=True)

    # bekannte CDN URL (Fallback)
    url = "https://ciner-live.ercdn.net/showturk/playlist.m3u8"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.showturk.com.tr/",
        "Origin": "https://www.showturk.com.tr"
    }

    try:
        r = requests.get(url, headers=headers, timeout=10)

        if r.status_code == 200 and "#EXTM3U" in r.text:
            print("✅ Stream gefunden")

            with open(OUTPUT, "w") as f:
                f.write(r.text)

            print(f"💾 gespeichert: {OUTPUT}")
        else:
            print(f"❌ Fehler: {r.status_code}")

    except Exception as e:
        print(f"❌ Exception: {e}")


if __name__ == "__main__":
    main()
