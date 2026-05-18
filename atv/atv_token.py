from playwright.sync_api import sync_playwright
from urllib.parse import urlparse, parse_qs, unquote

found = False

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    page = browser.new_page()

    def handle_response(response):
        global found

        url = response.url

        if "securevideotoken" in url and not found:
            found = True

            print("TOKEN URL:", url)

            parsed = urlparse(url)
            params = parse_qs(parsed.query)

            if "url" in params:
                stream = unquote(params["url"][0])

                print("STREAM:", stream)

                with open("atv/stream.txt", "w") as f:
                    f.write(stream)

    page.on("response", handle_response)

    page.goto(
        "https://www.atvavrupa.tv/canli-yayin",
        wait_until="domcontentloaded",
        timeout=60000
    )

    page.wait_for_timeout(15000)

    if not found:
        with open("atv/debug.txt", "w") as f:
            f.write("No token URL found")

        print("NO STREAM FOUND")

    browser.close()
