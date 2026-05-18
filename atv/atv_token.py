from playwright.sync_api import sync_playwright
import re

found = False

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=["--no-sandbox"]
    )

    page = browser.new_page(
        user_agent="Mozilla/5.0"
    )

    def handle_response(response):
        global found

        url = response.url

        if ".m3u8" in url and "atvavrupa" in url:
            print("FOUND:", url)

            with open("atv/stream.txt", "w") as f:
                f.write(url)

            found = True

    page.on("response", handle_response)

    try:
        page.goto(
            "https://www.atvavrupa.tv/canli-yayin",
            wait_until="domcontentloaded",
            timeout=30000
        )

        page.wait_for_timeout(15000)

    except Exception as e:
        print("ERROR:", e)

    browser.close()

if not found:
    with open("atv/debug.txt", "w") as f:
        f.write("No stream found")

    print("No stream found")
else:
    print("DONE")
