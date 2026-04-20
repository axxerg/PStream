import streamlink
import sys
import os
import json
import traceback

def info_to_text(stream_info, url):
    text = '#EXT-X-STREAM-INF:'
    if getattr(stream_info, "program_id", None):
        text += f'PROGRAM-ID={stream_info.program_id},'
    if getattr(stream_info, "bandwidth", None):
        text += f'BANDWIDTH={stream_info.bandwidth},'
    if getattr(stream_info, "codecs", None):
        codecs = ",".join(stream_info.codecs)
        text += f'CODECS="{codecs}",'
    if getattr(stream_info, "resolution", None):
        if stream_info.resolution and stream_info.resolution.width:
            text += f'RESOLUTION={stream_info.resolution.width}x{stream_info.resolution.height}'
    text += "\n" + url + "\n"
    return text

def get_streams(url, headers=None):
    # Erstellt die Session
    session = streamlink.Streamlink()
    
    # CRITICAL: Lade deine lokalen Plugins explizit
    plugin_dir = os.environ.get("STREAMLINK_PLUGIN_DIR")
    if plugin_dir and os.path.exists(plugin_dir):
        session.load_plugins(plugin_dir)

    default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    if headers:
        default_headers.update(headers)

    session.set_option("http-headers", default_headers)
    
    try:
        return session.streams(url)
    except streamlink.exceptions.NoPluginError:
        # Fallback für Star TV: Wenn kein Plugin gefunden wird, erzwinge HLS
        if url.startswith("https"):
            return session.streams("hls://" + url)
        raise

def build_playlists(streams):
    best_stream = streams.get("best")
    if not best_stream:
        return None, None

    mv = getattr(best_stream, "multivariant", None)

    # Fallback: Falls der Stream direkt geliefert wird (keine Master-Playlist)
    if not mv or not mv.playlists:
        # Wir extrahieren die URL des 'best' Objekts (oft ein HLSStream Objekt)
        stream_url = getattr(best_stream, "url", str(best_stream))
        # Baue eine einfache M3U8 Struktur
        simple_m3u = f"#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-STREAM-INF:BANDWIDTH=1280000,RESOLUTION=1280x720\n{stream_url}\n"
        return simple_m3u, simple_m3u

    previous_res_height = 0
    master_text = ""
    best_text = ""

    for playlist in mv.playlists:
        info = playlist.stream_info
        uri = playlist.uri
        if not info or info.video == "audio_only":
            continue

        sub_text = info_to_text(info, uri)
        height = getattr(info.resolution, "height", 0)

        if height > previous_res_height:
            master_text = sub_text + master_text
            best_text = sub_text
        else:
            master_text += sub_text
        previous_res_height = height

    if not master_text:
        return None, None

    header = "#EXTM3U\n"
    if mv.version:
        header += f"#EXT-X-VERSION:{mv.version}\n"

    return header + master_text, header + best_text

def main():
    print("=== Starting stream generation ===")
    config_file = sys.argv[1] if len(sys.argv) > 1 else "config/config.json"

    try:
        with open(config_file, "r") as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ Failed loading config: {e}")
        sys.exit(1)

    output_config = config["output"]
    channels = config["channels"]
    
    root_folder = output_config["folder"]
    best_folder = os.path.join(root_folder, output_config["bestFolder"])
    master_folder = os.path.join(root_folder, output_config["masterFolder"])

    os.makedirs(best_folder, exist_ok=True)
    os.makedirs(master_folder, exist_ok=True)

    success, fail = 0, 0

    for channel in channels:
        slug = channel.get("slug")
        url = channel.get("url")
        headers = channel.get("headers", {})

        print(f"\nProcessing: {slug}")
        
        try:
            streams = get_streams(url, headers=headers)
            if not streams:
                print("⚠️ No streams found")
                fail += 1
                continue

            master_text, best_text = build_playlists(streams)
            if not master_text:
                print("⚠️ Playlist build failed")
                fail += 1
                continue

            with open(os.path.join(master_folder, f"{slug}.m3u8"), "w") as f:
                f.write(master_text)
            with open(os.path.join(best_folder, f"{slug}.m3u8"), "w") as f:
                f.write(best_text)

            print("✅ Success")
            success += 1
        except Exception as e:
            print(f"❌ Error: {e}")
            fail += 1

    print(f"\n=== Summary ===\nSuccess: {success}\nFailed: {fail}\nTotal: {len(channels)}")
    if success == 0: sys.exit(1)

if __name__ == "__main__":
    main()
