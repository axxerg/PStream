import re
import json
from streamlink.plugin import Plugin, pluginmatcher
from streamlink.stream.hls import HLSStream

@pluginmatcher(re.compile(r"https?://(?:www\.)?showturk\.com\.tr/canli-yayin"))
class ShowTurk(Plugin):
    def _get_streams(self):
        # Wir setzen einen mobilen User-Agent, um Geoblocking zu minimieren
        mobile_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
        
        self.session.http.headers.update({
            "User-Agent": mobile_ua,
            "Accept-Language": "tr-TR,tr;q=0.9",
            "Referer": "https://www.showturk.com.tr/"
        })
        
        res = self.session.http.get(self.url)
        
        # Suche nach data-hope-video (auch mit flexiblen Anführungszeichen)
        match = re.search(r"data-hope-video=['\"](\{.*?\})['\"]", res.text)
        
        if match:
            try:
                video_conf = json.loads(match.group(1))
                hls_url = video_conf.get("media", {}).get("m3u8", [{}])[0].get("src")
                if hls_url:
                    return HLSStream.parse_variant_playlist(self.session, hls_url)
            except:
                pass

        # Letzter Versuch: Wenn nichts gefunden wurde, erzwinge den Standard-Stream
        # Manchmal akzeptiert das CDN den Zugriff, wenn wir eine gültige Referer-Session haben
        return HLSStream.parse_variant_playlist(self.session, "https://ciner-live.ercdn.net/showturk/playlist.m3u8")

__plugin__ = ShowTurk
