import re
import time
from streamlink.plugin import Plugin, pluginmatcher
from streamlink.stream.hls import HLSStream

@pluginmatcher(re.compile(r"https?://(?:www\.)?showturk\.com\.tr/canli-yayin"))
class ShowTurk(Plugin):
    def _get_streams(self):
        # Wir versuchen den Stream direkt zu erzwingen.
        # Da wir wissen, dass er auf ercdn liegt, nutzen wir die Basis-URL.
        # Der Server verlangt oft einen Zeitstempel (e=) und einen Token (st=).
        # Wir probieren es mit den Headern, die einen echten Browser simulieren.
        
        self.session.set_option("http-ssl-verify", False)
        
        # Basis URL ohne abgelaufenen Token
        hls_url = "https://ciner-live.ercdn.net/showturk/playlist.m3u8"
        
        # Wir geben die Header mit, die zwingend erforderlich sind
        headers = {
            "Referer": "https://www.showturk.com.tr/",
            "Origin": "https://www.showturk.com.tr",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        # Wir versuchen den Stream zu öffnen
        return HLSStream.parse_variant_playlist(self.session, hls_url, headers=headers)

__plugin__ = ShowTurk
