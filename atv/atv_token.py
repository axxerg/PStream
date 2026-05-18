from playwright.sync_api import sync_playwright

last_url = None

with sync_playwright() as p:

    browser = p.chromium.launch(
        headless=True,
        args=["--no-sandbox"]
    )

    page = browser.new_page(
        user_agent="Mozilla/5.0"
    )

    def handle_response(response):
        global last_url

        url = response.url

        # Nur echte ATV m3u8 Streams
        if (
            "trkvz-live.ercdn.net" in url
            and ".m3u8" in url
            and "_576p" not in url
        ):

            print("FOUND STREAM:")
            print(url)

            last_url = url

    page.on("response", handle_response)

    try:

        page.goto(
            "https://www.atvavrupa.tv/canli-yayin",
            wait_until="domcontentloaded",
            timeout=30000
        )

        # Warten bis Videoplayer lädt
        page.wait_for_timeout(20000)

    except Exception as e:

        with open("atv/debug.txt", "w") as f:
            f.write(str(e))

        print(e)

    browser.close()

if last_url:

    with open("atv/stream.txt", "w") as f:
        f.write(last_url)

    print("DONE")

else:

    with open("atv/debug.txt", "w") as f:
        f.write("NO STREAM FOUND")

    print("NO STREAM FOUND")
