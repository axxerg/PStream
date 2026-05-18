from playwright.sync_api import sync_playwright

with sync_playwright() as p:

    browser = p.chromium.launch(
        headless=True,
        args=["--no-sandbox"]
    )

    page = browser.new_page()

    def handle_response(response):

        url = response.url

        if (
            "m3u8" in url
            or "secure" in url
            or "player" in url
            or "video" in url
            or "playlist" in url
        ):

            print("\n====================")
            print("URL:")
            print(url)

            try:
                body = response.text()

                print("\nBODY:")
                print(body[:5000])

            except:
                pass

    page.on("response", handle_response)

    page.goto(
        "https://www.atvavrupa.tv/canli-yayin",
        wait_until="domcontentloaded"
    )

    page.wait_for_timeout(15000)

    browser.close()
