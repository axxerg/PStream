import re
from urllib.parse import urljoin

from streamlink.plugin import Plugin, pluginmatcher
from streamlink.stream.hls import HLSStream


@pluginmatcher(re.compile(r"https?://(?:www\.)?showturk\.com\.tr/canli-yayin"))
class ShowTurk(Plugin):

    _re_m3u8 = re.compile(r"""https?://[^"'\\\s]+\.m3u8[^"'\\\s]*""")

    def _get_streams(self):
        # Seite laden
        res = self.session.http.get(self.url)
        html = res.text

        # nach m3u8 suchen
        match = self._re_m3u8.search(html)

        if match:
            m3u8_url = match.group(0)
            return HLSStream.parse_variant_playlist(self.session, m3u8_url)

        return None


__plugin__ = ShowTurk
