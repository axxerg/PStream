import re
from streamlink.plugin import Plugin, pluginmatcher
from streamlink.stream.hls import HLSStream

@pluginmatcher(re.compile(r"https?://(?:www\.)?showturk\.com\.tr/canli-yayin"))
class ShowTurk(Plugin):
    def _get_streams(self):
        # Das ist der spezifische Server für Show Türk (nicht Show TV!)
        hls_url = "https://ciner-live.ercdn.net/showturk/playlist.m3u8"
        
        # Wir schalten die SSL-Prüfung aus, da GitHub-Runner oft Probleme mit 
        # türkischen CDN-Zertifikaten haben (403/500 Fehler).
        self.session.set_option("http-ssl-verify", False)
        
        # Wir senden die exakten Header mit, damit der Server glaubt, 
        # wir schauen über die offizielle Webseite.
        return HLSStream.parse_variant_playlist(self.session, hls_url, headers={
            "Referer": "https://www.showturk.com.tr/",
            "Origin": "https://www.showturk.com.tr",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        })

__plugin__ = ShowTurk
