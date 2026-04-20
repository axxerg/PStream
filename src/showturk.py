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

        match = self._re_data.search(html)
        if match:
            try:
                data = json.loads(match.group(1))
                m3u8 = data["media"]["m3u8"][0]["src"]

                self.logger.info(f"Found stream: {m3u8}")

                return HLSStream.parse_variant_playlist(
                    self.session,
                    m3u8,
                    headers={
                        "Referer": "https://www.showturk.com.tr/",
                        "User-Agent": "Mozilla/5.0"
                    }
                )
            except Exception as e:
                self.logger.error(f"Parse error: {e}")

        return None


__plugin__ = ShowTurk
