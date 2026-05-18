from playwright.sync_api import sync_playwright

found = False

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    page = browser.new_page()

    def handle_response(response):
        global found

        url = response.url

        if ".m3u8" in url and not found:
            found = True

            print("FOUND:", url)

            with open("atv/stream.txt", "w") as f:
                f.write(url)

    page.on("response", handle_response)

    page.goto(
        "https://www.atvavrupa.tv/canli-yayin",
        wait_until="domcontentloaded",
        timeout=60000
    )

    page.wait_for_timeout(20000)

    if not found:
        with open("atv/debug.txt", "w") as f:
            f.write("No m3u8 request found")

        print("NO STREAM FOUND")

    browser.close()
