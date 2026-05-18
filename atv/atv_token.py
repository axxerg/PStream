from playwright.sync_api import sync_playwright
import re

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    page = browser.new_page()

    page.goto(
        "https://www.atvavrupa.tv/canli-yayin",
        wait_until="domcontentloaded",
        timeout=60000
    )

    page.wait_for_timeout(10000)

    content = page.content()

    with open("atv/debug.txt", "w", encoding="utf-8") as f:
        f.write(content)

    urls = re.findall(r'https://[^"]+\.m3u8[^"]*', content)

    found = False

    for url in urls:
        if ".m3u8" in url:
            with open("atv/stream.txt", "w") as f:
                f.write(url)

            print("FOUND:", url)
            found = True
            break

    if not found:
        print("NO M3U8 FOUND")

    browser.close()
