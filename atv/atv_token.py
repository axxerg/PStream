from playwright.sync_api import sync_playwright
import re

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    page = browser.new_page()

    urls = []

    def handle_response(response):
        url = response.url

        if ".m3u8" in url:
            urls.append(url)

    page.on("response", handle_response)

    page.goto(
        "https://www.atvavrupa.tv/canli-yayin",
        wait_until="networkidle",
        timeout=60000
    )

    page.wait_for_timeout(10000)

    browser.close()

if urls:
    stream = urls[0]

    with open("atv/stream.txt", "w") as f:
        f.write(stream)

    print("FOUND:", stream)

else:
    print("No stream found")
