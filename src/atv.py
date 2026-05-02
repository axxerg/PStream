#!/usr/bin/env python3
from flask import Flask, Response
import requests
import re
import html

app = Flask(__name__)

PAGE_URL = "https://www.atvavrupa.tv/canli-yayin"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.atvavrupa.tv/",
    "Connection": "keep-alive",
}

TOKEN_RE = re.compile(
    r"https:\/\/trkvz-live\.ercdn\.net\/atvavrupa\/atvavrupa\.m3u8\?st=[^\"']+",
    re.I
)


def resolve_stream():
    r = requests.get(PAGE_URL, headers=HEADERS, timeout=10)
    r.raise_for_status()

    source = html.unescape(r.text)
    match = TOKEN_RE.search(source)

    if not match:
        return None

    return match.group(0).replace("\\/", "/")


@app.route("/atv.m3u8")
def atv():
    try:
        url = resolve_stream()

        if not url:
            return Response("stream unavailable", status=503)

        return Response(
            f"#EXTM3U\n{url}\n",
            mimetype="application/vnd.apple.mpegurl"
        )

    except Exception:
        return Response("stream unavailable", status=503)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
