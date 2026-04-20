import re
import json
from streamlink.plugin import Plugin, pluginmatcher
from streamlink.stream import HLSStream

@pluginmatcher(re.compile(r"https?://(?:www\.)?showturk\.com\.tr/canli-yayin"))
class ShowTurk(Plugin):
    def _get_streams(self):
        # 1. Die Webseite laden
        res = self.session.http.get(self.url)
        
        # 2. Den Token und die URL aus dem 'data-hope-video' Attribut extrahieren
        # Wir suchen nach dem JSON-Inhalt innerhalb der einfachen Anführungszeichen
        match = re.search(r"data-hope-video='(\{.*?\})'", res.text)
        
        if match:
            try:
                video_conf = json.loads(match.group(1))
                # Der Pfad im JSON: media -> m3u8 -> erstes Element -> src
                hls_url = video_conf.get("media", {}).get("m3u8", [{}])[0].get("src")
                
                if hls_url:
                    # SSL-Verifizierung ausschalten, falls der Runner Probleme hat
                    self.session.set_option("http-ssl-verify", False)
                    
                    return HLSStream.parse_variant_playlist(self.session, hls_url, headers={
                        "Referer": "https://www.showturk.com.tr/",
                        "Origin": "https://www.showturk.com.tr",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                    })
            except (json.JSONDecodeError, KeyError, IndexError) as e:
                self.logger.error(f"Fehler beim Parsen der Video-Daten: {e}")

        return
        
__plugin__ = ShowTurk
