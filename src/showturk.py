import re
from streamlink.plugin import Plugin, pluginmatcher
from streamlink.stream import HLSStream

@pluginmatcher(re.compile(r"https?://(?:www\.)?showturk\.com\.tr/canli-yayin"))
class ShowTurk(Plugin):
    def _get_streams(self):
        # Der direkte Endpunkt für Show Türk
        hls_url = "https://ciner-live.ercdn.net/showturk/playlist.m3u8"
        
        # Wir übergeben die notwendigen Header direkt an den HLS-Fetcher
        return HLSStream.parse_variant_playlist(self.session, hls_url, headers={
            "Referer": "https://www.showturk.com.tr/",
            "Origin": "https://www.showturk.com.tr"
        })

__plugin__ = ShowTurk
