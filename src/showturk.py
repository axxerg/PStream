import re
import json
from streamlink.plugin import Plugin, pluginmatcher
from streamlink.stream.hls import HLSStream


@pluginmatcher(re.compile(r"https?://(?:www\.)?showturk\.com\.tr/canli-yayin"))
class ShowTurk(Plugin):

    _re_data = re.compile(r"data-hope-video='(.*?)'")

    def _get_streams(self):
        res = self.session.http.get(self.url)
        html = res.text

        # 1. Versuch: echte m3u8 aus JSON
        match = self._re_data.search(html)
        if match:
            try:
                data = json.loads(match.group(1))
                m3u8 = data["media"]["m3u8"][0]["src"]

                return HLSStream.parse_variant_playlist(self.session, m3u8)
            except Exception:
                pass

        # 2. Fallback (deine harte URL)
        fallback = "https://ciner-live.ercdn.net/showturk/playlist.m3u8"

        return HLSStream.parse_variant_playlist(
            self.session,
            fallback,
            headers={
                "Referer": "https://www.showturk.com.tr/",
                "User-Agent": "Mozilla/5.0"
            }
        )


__plugin__ = ShowTurk
