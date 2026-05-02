#!/usr/bin/env python3
"""
ATV Extractor
- nutzt Streamlink nur zum Finden der besten Variante
- lädt danach die echte Variant-Playlist
- normalisiert relative URLs
- speichert eine direkt nutzbare ATV M3U8
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
import streamlink
from streamlink.exceptions import NoPluginError, StreamlinkError


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def create_streamlink_session(headers: dict | None = None) -> streamlink.Streamlink:
    session = streamlink.Streamlink()

    plugin_dir = os.getenv("STREAMLINK_PLUGIN_DIR")
    if plugin_dir and os.path.isdir(plugin_dir):
        session.load_plugins(plugin_dir)

    merged_headers = {"User-Agent": DEFAULT_USER_AGENT}
    if headers:
        merged_headers.update(headers)

    session.set_option("http-headers", merged_headers)
    session.set_option("http-timeout", 20)
    session.set_option("stream-timeout", 20)

    return session


def get_streams(url: str, headers: dict | None = None) -> dict:
    session = create_streamlink_session(headers)

    try:
        return session.streams(url)
    except NoPluginError:
        if url.startswith(("http://", "https://")):
            return session.streams(f"hls://{url}")
        raise
    except StreamlinkError as e:
        raise RuntimeError(f"Streamlink Fehler: {e}") from e


def get_best_variant_url(streams: dict) -> str | None:
    best_stream = streams.get("best")
    if not best_stream:
        return None

    multivariant = getattr(best_stream, "multivariant", None)

    # direkter HLS Stream ohne Varianten
    if not multivariant or not getattr(multivariant, "playlists", None):
        return getattr(best_stream, "url", None)

    best_url = None
    best_height = -1

    for playlist in multivariant.playlists:
        info = getattr(playlist, "stream_info", None)
        uri = getattr(playlist, "uri", None)

        if not info or not uri:
            continue

        if getattr(info, "video", None) == "audio_only":
            continue

        resolution = getattr(info, "resolution", None)
        height = getattr(resolution, "height", 0) if resolution else 0

        if height > best_height:
            best_height = height
            best_url = uri

    return best_url


def normalize_playlist(content: str, playlist_url: str) -> str:
    """
    Wandelt relative Segment- oder Sub-Playlist-URLs in absolute URLs um.
    """
    lines = []
    base = playlist_url.rsplit("/", 1)[0] + "/"

    for line in content.splitlines():
        stripped = line.strip()

        if stripped and not stripped.startswith("#"):
            line = urljoin(base, stripped)

        lines.append(line)

    return "\n".join(lines) + "\n"


def fetch_playlist(url: str, headers: dict | None = None) -> str:
    req_headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "*/*",
        "Connection": "keep-alive",
    }

    if headers:
        req_headers.update(headers)

    with requests.Session() as session:
        r = session.get(url, headers=req_headers, timeout=(5, 15))
        r.raise_for_status()

        if "#EXTM3U" not in r.text:
            raise ValueError("Keine gültige M3U8 erhalten")

        return normalize_playlist(r.text, r.url)


def save_playlist(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")

    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)

    os.replace(tmp, path)


def process_channel(channel: dict, output_dir: Path) -> bool:
    slug = channel.get("slug")
    url = channel.get("url")
    headers = channel.get("headers", {})

    if not slug or not url:
        print(f"❌ Ungültiger Channel: {channel}")
        return False

    try:
        print(f"▶ Verarbeite: {slug}")

        streams = get_streams(url, headers)
        if not streams:
            print("  ❌ Keine Streams gefunden")
            return False

        best_url = get_best_variant_url(streams)
        if not best_url:
            print("  ❌ Keine Variant-URL gefunden")
            return False

        print(f"  🔗 Beste Variante: {best_url}")

        playlist = fetch_playlist(best_url, headers)
        save_playlist(output_dir / f"{slug}.m3u8", playlist)

        print(f"  ✅ Gespeichert: {output_dir / f'{slug}.m3u8'}")
        return True

    except requests.HTTPError as e:
        print(f"  ❌ HTTP Fehler: {e}")
        return False

    except requests.RequestException as e:
        print(f"  ❌ Netzwerkfehler: {e}")
        return False

    except Exception as e:
        print(f"  ❌ Fehler: {type(e).__name__}: {e}")
        return False


def main() -> int:
    print("=== ATV Extractor ===")

    config_path = sys.argv[1] if len(sys.argv) > 1 else "config/config.json"

    try:
        config = load_json(config_path)
    except Exception as e:
        print(f"❌ Config Fehler: {e}")
        return 1

    output_dir = Path(config["output"]["folder"])
    channels = config["channels"]

    success = 0
    failed = 0

    for channel in channels:
        if process_channel(channel, output_dir):
            success += 1
        else:
            failed += 1

    print("\n=== Summary ===")
    print(f"Success: {success}")
    print(f"Failed:  {failed}")
    print(f"Total:   {len(channels)}")

    return 0 if success > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
