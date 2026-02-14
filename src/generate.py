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
    session = streamlink.Streamlink()

    default_headers = {
        "User-Agent": "Mozilla/5.0"
    }

    if headers:
        default_headers.update(headers)

    session.set_option("http-headers", default_headers)

    return session.streams(url)


def build_playlists(streams):
    best_stream = streams.get("best")
    if not best_stream:
        return None, None

    mv = getattr(best_stream, "multivariant", None)

    # Falls keine Variant Playlist existiert
    if not mv or not mv.playlists:
        return None, None

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

    if mv.version:
        master_text = f"#EXT-X-VERSION:{mv.version}\n" + master_text
        best_text = f"#EXT-X-VERSION:{mv.version}\n" + best_text

    master_text = "#EXTM3U\n" + master_text
    best_text = "#EXTM3U\n" + best_text

    return master_text, best_text


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

    success = 0
    fail = 0

    for channel in channels:
        slug = channel.get("slug")
        url = channel.get("url")
        headers = channel.get("headers", {})

        print(f"\nProcessing: {slug}")
        print(f"URL: {url}")

        try:
            streams = get_streams(url, headers=headers)

            if not streams:
                print("⚠️ No streams found")
                fail += 1
                continue

            master_text, best_text = build_playlists(streams)

            if not master_text:
                print("⚠️ No multivariant playlist available")
                fail += 1
                continue

            master_path = os.path.join(master_folder, f"{slug}.m3u8")
            best_path = os.path.join(best_folder, f"{slug}.m3u8")

            with open(master_path, "w") as f:
                f.write(master_text)

            with open(best_path, "w") as f:
                f.write(best_text)

            print("✅ Success")
            success += 1

        except Exception as e:
            print(f"❌ Error: {e}")
            print(traceback.format_exc())
            fail += 1

    print("\n=== Summary ===")
    print(f"Success: {success}")
    print(f"Failed: {fail}")
    print(f"Total: {len(channels)}")

    # Wenn ALLE fehlschlagen -> CI soll failen
    if success == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
