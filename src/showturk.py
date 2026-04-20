import re
import json
from streamlink.plugin import Plugin, pluginmatcher
from streamlink.stream.hls import HLSStream

@pluginmatcher(re.compile(r"https?://(?:www\.)?showturk\.com\.tr/canli-yayin"))
class ShowTurk(Plugin):
    def _get_streams(self):
        # 1. Seite mit getürktem User-Agent laden
        res = self.session.http.get(self.url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        })
        
        # 2. Versuch: Suche im JSON-Block (wie zuvor)
        match = re.search(r"data-hope-video='(\{.*?\})'", res.text)
        if match:
            try:
                video_conf = json.loads(match.group(1))
                hls_url = video_conf.get("media", {}).get("m3u8", [{}])[0].get("src")
                if hls_url:
                    return HLSStream.parse_variant_playlist(self.session, hls_url)
            except:
                pass

        # 3. Versuch: "Brute Force" Suche nach M3U8 URLs auf den Ciner-Servern
        # Wir suchen direkt nach Links, die auf .m3u8 enden und 'ciner' oder 'ercdn' enthalten
        links = re.findall(r'https?://[^\s\'"]+showturk[^\s\'"]+\.m3u8[^\s\'"]*', res.text)
        for link in links:
            # Entferne HTML-Escaping (falls vorhanden)
            clean_link = link.replace("\\/", "/").replace("&amp;", "&")
            return HLSStream.parse_variant_playlist(self.session, clean_link)

__plugin__ = ShowTurk
