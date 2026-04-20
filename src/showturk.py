import re
import json
from streamlink.plugin import Plugin, pluginmatcher
from streamlink.stream import HLSStream

@pluginmatcher(re.compile(r"https?://(?:www\.)?showturk\.com\.tr/canli-yayin"))
class ShowTurk(Plugin):
    def _get_streams(self):
        # 1. Webseite laden
        res = self.session.http.get(self.url)
        
        # 2. Suche nach der Stream-Konfiguration im JavaScript (typisch für Ciner Media)
        match = re.search(r'ht_stream_data\s*=\s*(\{.*?\});', res.text)
        if match:
            try:
                data = json.loads(match.group(1))
                # Wir nehmen die HLS-URL aus den Daten
                hls_url = data.get("ht_stream_m3u8")
                if hls_url:
                    return HLSStream.parse_variant_playlist(self.session, hls_url, headers={
                        "Referer": self.url,
                        "Origin": "https://www.showturk.com.tr"
                    })
            except:
                pass

        # 3. Fallback: Falls JS-Parsing scheitert, suche nach irgendeiner m3u8 auf ercdn
        match = re.search(r'["\'](https?://[^"\']+/showturk/[^"\']+\.m3u8[^"\']*)["\']', res.text)
        if match:
            return HLSStream.parse_variant_playlist(self.session, match.group(1))

__plugin__ = ShowTurk
