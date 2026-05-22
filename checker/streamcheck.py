import asyncio
import aiohttp
import os

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0 Safari/537.36"
}

TIMEOUT = aiohttp.ClientTimeout(total=1.5)  # HARTE DEADLINE

async def check_url(session, url):
    try:
        async with session.head(url, allow_redirects=True) as r:
            if r.status in (200, 301, 302):
                return url, True
    except:
        pass

    try:
        async with session.get(url) as r:
            text = await r.text()
            if "#EXTM3U" in text or ".m3u8" in text or ".ts" in text:
                return url, True
    except:
        pass

    return url, False


def load_playlist(path):
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    entries = []
    last_extinf = None

    for line in lines:
        line = line.strip()

        if line.startswith("#EXTINF"):
            last_extinf = line
        elif line.startswith("http"):
            if last_extinf is None:
                last_extinf = "#EXTINF:-1 ,TEST"
            entries.append((last_extinf, line))
            last_extinf = None

    return entries


def sort_entries(entries):
    return sorted(entries, key=lambda e: e[0].split(",")[-1].strip().lower())


def write_output(path, entries):
    with open(path, "w", encoding="utf-8") as f:
        for extinf, url in entries:
            f.write(extinf + "\n")
            f.write(url + "\n\n")


async def main():
    input_file = "checker/playlist.m3u"
    output_file = "checker/reachable.txt"
    unreachable_file = "checker/unreachable.txt"

    entries = load_playlist(input_file)
    urls = [url for _, url in entries]

    print(f"Prüfe {len(urls)} Streams… (ASYNC)")

    async with aiohttp.ClientSession(headers=HEADERS, timeout=TIMEOUT) as session:
        tasks = [check_url(session, url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=False)

    reachable = []
    unreachable = []

    for (extinf, url), (_, ok) in zip(entries, results):
        if ok:
            reachable.append((extinf, url))
        else:
            unreachable.append((extinf, url))

    reachable = sort_entries(reachable)
    unreachable = sort_entries(unreachable)

    write_output(output_file, reachable)
    write_output(unreachable_file, unreachable)

    print(f"FERTIG! {len(reachable)} OK, {len(unreachable)} FAILED")


if __name__ == "__main__":
    asyncio.run(main())
