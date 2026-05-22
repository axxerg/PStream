import os
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

HEADERS = {
    'User-Agent':
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/120.0 Safari/537.36'
}

def check_url(url):
    try:
        # HEAD Check (0.3 Sekunden)
        try:
            r = requests.head(url, headers=HEADERS, timeout=0.3, allow_redirects=True)
            head_ok = r.status_code in (200, 301, 302)
        except:
            head_ok = False

        # GET Check (0.5 Sekunden)
        try:
            content = requests.get(url, headers=HEADERS, timeout=0.5).text
        except:
            content = ""

        m3u_ok = "#EXTM3U" in content
        master_ok = ".m3u8" in content
        seg_ok = any(x in content for x in [".ts", ".m4s", ".aac"])

        return url, (head_ok or m3u_ok or master_ok or seg_ok)

    except:
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
    def key_func(entry):
        extinf, _ = entry
        if "," in extinf:
            return extinf.split(",")[-1].strip().lower()
        return extinf.lower()

    return sorted(entries, key=key_func)


def write_output(path, entries):
    with open(path, "w", encoding="utf-8") as f:
        for extinf, url in entries:
            f.write(extinf + "\n")
            f.write(url + "\n\n")


if __name__ == "__main__":
    input_file = "checker/playlist.m3u"
    output_file = "checker/reachable.txt"
    unreachable_file = "checker/unreachable.txt"

    print("Lade Playlist…")
    entries = load_playlist(input_file)

    urls = [url for _, url in entries]

    print(f"Prüfe {len(urls)} Streams parallel…")

    reachable = []
    unreachable = []

    # 50 Threads → ultraschnell
    with ThreadPoolExecutor(max_workers=50) as executor:
        future_map = {executor.submit(check_url, url): (extinf, url) for extinf, url in entries}

        for future in as_completed(future_map):
            extinf, url = future_map[future]
            _, ok = future.result()

            if ok:
                reachable.append((extinf, url))
            else:
                unreachable.append((extinf, url))

    reachable = sort_entries(reachable)
    unreachable = sort_entries(unreachable)

    write_output(output_file, reachable)
    write_output(unreachable_file, unreachable)

    print(f"FERTIG! {len(reachable)} OK, {len(unreachable)} FAILED")
    print(f"Ergebnis gespeichert in: {output_file}")
