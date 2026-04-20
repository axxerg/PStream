import re
from streamlink.plugin import Plugin, pluginmatcher
from streamlink.stream import HLSStream

@pluginmatcher(re.compile(r"https?://(?:www\.)?showturk\.com\.tr/canli-yayin"))
class ShowTurk(Plugin):
    def _get_streams(self):
        # 1. Webseite laden, um Session/Cookies zu initiieren
        res = self.session.http.get(self.url)
        
        # 2. Suche nach der m3u8 URL im Quelltext (ShowTurk nutzt oft ht_stream_data)
        # Wir suchen nach einem Muster, das auf .m3u8 endet
        match = re.search(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', res.text)
        
        if match:
            hls_url = match.group(1).replace("\\/", "/")
            return HLSStream.parse_variant_playlist(self.session, hls_url, headers={
                "Referer": self.url,
                "Origin": "https://www.showturk.com.tr",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            })
        
        # Fallback auf den direkten Link, falls Regex scheitert
        return HLSStream.parse_variant_playlist(self.session, "https://ciner-live.ercdn.net/showturk/playlist.m3u8")

__plugin__ = ShowTurk
