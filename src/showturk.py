import re
from streamlink.plugin import Plugin, pluginmatcher
from streamlink.stream.hls import HLSStream

@pluginmatcher(re.compile(r"https?://(?:www\.)?showturk\.com\.tr/canli-yayin"))
class ShowTurk(Plugin):
    def _get_streams(self):
        # Wir greifen direkt die Master-Playlist an. 
        # Ciner-Sender haben oft diesen Pfad als Fallback.
        hls_url = "https://ciner-live.ercdn.net/showturk/playlist.m3u8"
        
        # SSL-Prüfung deaktivieren (wichtig für Runner in den USA)
        self.session.set_option("http-ssl-verify", False)
        
        # Wir tarnen uns als lokaler türkischer Browser
        return HLSStream.parse_variant_playlist(self.session, hls_url, headers={
            "Referer": "https://www.showturk.com.tr/",
            "Origin": "https://www.showturk.com.tr",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "X-Forwarded-For": "31.145.120.120" # Wir täuschen eine türkische IP vor
        })

__plugin__ = ShowTurk
