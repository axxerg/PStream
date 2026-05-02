#!/usr/bin/env python3
"""
ATV Avrupa URL Writer
- schreibt die stabile ATV Avrupa Stream-URL direkt in eine M3U8
- kein Parsing
- kein Token Resolver
- kein CDN Fetch
"""

import os

OUTPUT = "output/atv.m3u8"
STREAM_URL = "https://trkvz-live.ercdn.net/atvavrupa/atvavrupa.m3u8"


def save_playlist() -> None:
    os.makedirs("output", exist_ok=True)
    tmp = OUTPUT + ".tmp"

    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"#EXTM3U\n{STREAM_URL}\n")

    os.replace(tmp, OUTPUT)


def main() -> int:
    try:
        save_playlist()
        print(f"💾 gespeichert: {OUTPUT}")
        return 0

    except OSError as e:
        print(f"❌ Datei Fehler: {e}")
        return 1

    except Exception as e:
        print(f"❌ Unerwarteter Fehler: {type(e).__name__}: {e}")
        return 99


if __name__ == "__main__":
    raise SystemExit(main())
