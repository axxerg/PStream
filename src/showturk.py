import re
import json
from streamlink.plugin import Plugin, pluginmatcher
from streamlink.stream.hls import HLSStream

@pluginmatcher(re.compile(r"https?://(?:www\.)?showturk\.com\.tr/canli-yayin"))
class ShowTurk(Plugin):
    def _get_streams(self):
        # 1. Fetch the page 📄
        res = self.session.http.get(self.url)
        
        # 2. Extract the JSON from data-hope-video 🔍
        # Look for the content between data-hope-video=' and '
        match = re.search(r"data-hope-video='(\{.*?\})'", res.text)
        
        if match:
            try:
                video_conf = json.loads(match.group(1))
                # Navigate the JSON structure: media -> m3u8 -> [0] -> src
                playlist_url = video_conf.get("media", {}).get("m3u8", [{}])[0].get("src")
                
                if playlist_url:
                    # Return the stream with the dynamic token included in the URL 🔑
                    return HLSStream.parse_variant_playlist(self.session, playlist_url, headers={
                        "Referer": self.url,
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                    })
            except (json.JSONDecodeError, KeyError, IndexError):
                pass
        
        return
        
__plugin__ = ShowTurk
