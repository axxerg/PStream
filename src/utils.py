import os
import json
from dataclasses import dataclass
from typing import Dict, Any, Tuple, Optional

import streamlink


# ----------------------------
# Config / Output Paths
# ----------------------------

@dataclass
class OutputPaths:
    root: str
    best_dir: str
    master_dir: str


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_output_folders(output_cfg: Dict[str, Any], cwd: Optional[str] = None) -> OutputPaths:
    """
    output_cfg erwartet:
      { "folder": "output", "bestFolder": "best", "masterFolder": "master" }
    """
    base = cwd or os.getcwd()

    root = os.path.join(base, output_cfg["folder"])
    best_dir = os.path.join(root, output_cfg["bestFolder"])
    master_dir = os.path.join(root, output_cfg["masterFolder"])

    os.makedirs(best_dir, exist_ok=True)
    os.makedirs(master_dir, exist_ok=True)

    return OutputPaths(root=root, best_dir=best_dir, master_dir=master_dir)


# ----------------------------
# Streamlink Session / Streams
# ----------------------------

def make_streamlink_session(headers: Optional[Dict[str, str]] = None) -> streamlink.Streamlink:
    """
    Baut eine Streamlink-Session mit http-headers.
    Perfekt für Seiten, die Referer / User-Agent brauchen.
    """
    session = streamlink.Streamlink()

    default_headers = {
        "User-Agent": "Mozilla/5.0",
    }

    if headers:
        default_headers.update(headers)

    session.set_option("http-headers", default_headers)

    return session


def fetch_streams(url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Liefert streamlink.streams()-ähnliches dict, aber über eigene Session,
    damit pro Channel headers sauber funktionieren.
    """
    session = make_streamlink_session(headers=headers)
    return session.streams(url)


# ----------------------------
# M3U8 Building
# ----------------------------

def stream_info_to_extinf(stream_info, url: str) -> str:
    """
    Baut eine #EXT-X-STREAM-INF Zeile aus Streamlink stream_info.
    """
    text = "#EXT-X-STREAM-INF:"

    program_id = getattr(stream_info, "program_id", None)
    if program_id:
        text += f"PROGRAM-ID={program_id},"

    bandwidth = getattr(stream_info, "bandwidth", None)
    if bandwidth:
        text += f"BANDWIDTH={bandwidth},"

    codecs = getattr(stream_info, "codecs", None)
    if codecs:
        text += f'CODECS="{",".join(codecs)}",'

    res = getattr(stream_info, "resolution", None)
    if res and getattr(res, "width", None) and getattr(res, "height", None):
        text += f"RESOLUTION={res.width}x{res.height}"

    return text + "\n" + url + "\n"


def build_master_and_best(streams: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """
    Erzeugt master_text und best_text aus streams['best'].multivariant.playlists
    (wie in deinem Script). Gibt (None, None) zurück, wenn nicht möglich.
    """
    best_stream = streams.get("best")
    if not best_stream:
        return None, None

    mv = getattr(best_stream, "multivariant", None)
    if not mv or not getattr(mv, "playlists", None):
        return None, None

    master_text = ""
    best_text = ""

    # wir sortieren nach Höhe absteigend (best oben)
    def height_of(pl):
        info = getattr(pl, "stream_info", None)
        res = getattr(info, "resolution", None) if info else None
        return getattr(res, "height", 0) if res else 0

    playlists = sorted(mv.playlists, key=height_of, reverse=True)

    for i, playlist in enumerate(playlists):
        info = playlist.stream_info
        if not info:
            continue

        # audio_only ignorieren
        if getattr(info, "video", None) == "audio_only":
            continue

        sub = stream_info_to_extinf(info, playlist.uri)
        master_text += sub
        if i == 0:
            best_text = sub

    if not master_text or not best_text:
        return None, None

    # optional VERSION header
    version = getattr(mv, "version", None)
    if version:
        master_text = f"#EXT-X-VERSION:{version}\n" + master_text
        best_text = f"#EXT-X-VERSION:{version}\n" + best_text

    master_text = "#EXTM3U\n" + master_text
    best_text = "#EXTM3U\n" + best_text

    return master_text, best_text


# ----------------------------
# File IO
# ----------------------------

def write_text_file(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def remove_if_exists(path: str) -> None:
    try:
        if os.path.isfile(path):
            os.remove(path)
    except Exception:
        # bewusst leise: cleanup darf nicht den run killen
        pass
