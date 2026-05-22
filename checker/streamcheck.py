import os
import requests
from concurrent.futures import ThreadPoolExecutor

# Browser Header (wichtig für türkische Streams)
HEADERS = {
    'User-Agent':
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/120.0 Safari/537.36'
}

# Schneller HEAD + GET Check
def check_url(url):
    try:
        # HEAD Check (1 Sekunde)
        r = requests.head(url, headers=HEADERS, timeout=1, allow_redirects=True)
        head_ok = r.status_code in (200, 301, 302)

        # GET Check (2 Sekunden)
        try:
            content = requests.get(url, headers=HEADERS, timeout=2).text
        except:
            content = ""

        m3u_ok = "#EXTM3U" in content
        master_ok = ".m3u8" in content
        seg_ok = any(x in content for x in [".ts", ".m4s", ".aac"])

        return url, (head_ok or m3u_ok or master_ok or seg_ok)

    except Exception:
        return url, False


# Playlist einlesen und EXTINF + URL paaren
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


# Sortieren nach Sendername (Text nach letztem Komma)
def sort_entries(entries):
    def key_func(entry):
        extinf, _ = entry
        if "," in extinf:
            return extinf.split(",")[-1].strip().lower()
        return extinf.lower()

    return sorted(entries, key=key_func)


# Schreiben der funktionierenden Streams
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

    # Parallel prüfen (10 Threads)
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(check_url, urls))

    reachable = []
    unreachable = []

    for (extinf, url), (_, ok) in zip(entries, results):
        if ok:
            reachable.append((extinf, url))
        else:
            unreachable.append((extinf, url))

    # Sortieren
    reachable = sort_entries(reachable)
    unreachable = sort_entries(unreachable)

    # Schreiben
    write_output(output_file, reachable)
    write_output(unreachable_file, unreachable)

    print(f"FERTIG! {len(reachable)} OK, {len(unreachable)} FAILED")
    print(f"Ergebnis gespeichert in: {output_file}")
