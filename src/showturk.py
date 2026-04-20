import re
from streamlink.plugin import Plugin, pluginmatcher
from streamlink.stream import HLSStream

@pluginmatcher(re.compile(r"https?://(?:www\.)?showturk\.com\.tr/canli-yayin"))
class ShowTurk(Plugin):
    def _get_streams(self):
        # 1. Die Webseite laden, um den Token zu finden
        res = self.session.http.get(self.url)
        
        # 2. Suche nach der m3u8 URL im Quelltext (ShowTurk nutzt oft ht_stream_data oder ähnliche JS-Variablen)
        match = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', res.text)
        
        if match:
            hls_url = match.group(1).replace("\\/", "/")
            # Sicherstellen, dass wir nicht aus Versehen ShowTV erwischen
            if "showturk" in hls_url or "show-turk" in hls_url:
                return HLSStream.parse_variant_playlist(self.session, hls_url, headers={
                    "Referer": self.url,
                    "Origin": "https://www.showturk.com.tr"
                })

        # Fallback: Falls Regex fehlschlägt, direkter Versuch mit Referer
        return HLSStream.parse_variant_playlist(self.session, 
            "https://ciner-live.ercdn.net/showturk/playlist.m3u8", 
            headers={"Referer": self.url})

__plugin__ = ShowTurk
