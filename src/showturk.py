import re
import json
from streamlink.plugin import Plugin, pluginmatcher
from streamlink.stream.hls import HLSStream

@pluginmatcher(re.compile(r"https?://(?:www\.)?showturk\.com\.tr/canli-yayin"))
class ShowTurk(Plugin):
    def _get_streams(self):
        # 1. Die Webseite mit Browser-Headern laden
        self.session.set_option("http-ssl-verify", False)
        res = self.session.http.get(self.url)
        
        # 2. Den dynamischen Token aus dem 'data-hope-video' Attribut extrahieren
        # Wir suchen nach dem Inhalt zwischen data-hope-video=' und '
        match = re.search(r"data-hope-video='(\{.*?\})'", res.text)
        
        if match:
            try:
                # Das gefundene JSON in ein Python-Objekt umwandeln
                video_conf = json.loads(match.group(1))
                
                # Die M3U8-URL aus der Struktur extrahieren:
                # media -> m3u8 -> [0] -> src
                hls_url = video_conf.get("media", {}).get("m3u8", [{}])[0].get("src")
                
                if hls_url:
                    # Wir geben die Stream-URL mit den notwendigen Headern zurück
                    return HLSStream.parse_variant_playlist(self.session, hls_url, headers={
                        "Referer": self.url,
                        "Origin": "https://www.showturk.com.tr",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                    })
            except (json.JSONDecodeError, KeyError, IndexError) as e:
                self.logger.error(f"Fehler beim Verarbeiten der Video-Daten: {e}")

        # Fallback: Falls die Webseite blockiert, versuchen wir den direkten Link
        # (Erfolg hierbei hängt stark von der IP-Sperre ab)
        fallback_url = "https://ciner-live.ercdn.net/showturk/playlist.m3u8"
        return HLSStream.parse_variant_playlist(self.session, fallback_url, headers={"Referer": self.url})

__plugin__ = ShowTurk
