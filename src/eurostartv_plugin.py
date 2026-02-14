import re
from urllib.parse import urljoin

from streamlink.plugin import Plugin, pluginmatcher
from streamlink.stream.hls import HLSStream


@pluginmatcher(re.compile(r"https?://(www\.)?eurostartv\.com\.tr/canli-izle/?"))
class EurostarTV(Plugin):
    """
    Streamlink-Plugin für https://www.eurostartv.com.tr/canli-izle

    Ziel:
    - Seite laden
    - eine öffentliche .m3u8 URL finden (direkt / über iframe / über player-config)
    - Variant Playlist parsen und Streams zurückgeben
    """

    # Muster für eine m3u8 irgendwo im HTML/JS
    _re_m3u8 = re.compile(r"""(?P<url>https?://[^"'\\\s]+\.m3u8[^"'\\\s]*)""", re.IGNORECASE)

    # iframe src finden
    _re_iframe = re.compile(r"""<iframe[^>]+src=["'](?P<src>[^"']+)["']""", re.IGNORECASE)

    # Beispielhafte Player-Konfig Keys (kommt häufig vor)
    _re_source_url = re.compile(
        r"""(?:
              source\s*:\s*\{\s*src\s*:\s*["'](?P<src1>https?://[^"']+)["'] |
              file\s*:\s*["'](?P<src2>https?://[^"']+)["'] |
              hls\s*:\s*["'](?P<src3>https?://[^"']+)["']
            )""",
        re.IGNORECASE | re.VERBOSE,
    )

    def _fetch(self, url):
        # Streamlink session.http nutzt requests; Referer/UA kannst du außerhalb via Session-Optionen setzen
        return self.session.http.get(url)

    def _find_m3u8_in_text(self, text):
        m = self._re_m3u8.search(text or "")
        return m.group("url") if m else None

    def _find_iframe_url(self, html, base_url):
        m = self._re_iframe.search(html or "")
        if not m:
            return None
        src = m.group("src")
        return urljoin(base_url, src)

    def _find_player_source_url(self, text):
        m = self._re_source_url.search(text or "")
        if not m:
            return None
        return m.group("src1") or m.group("src2") or m.group("src3")

    def _get_streams(self):
        # 1) Hauptseite laden
        res = self._fetch(self.url)
        html = res.text

        # 2) Direkte m3u8 im HTML/JS?
        m3u8 = self._find_m3u8_in_text(html)
        if m3u8:
            return HLSStream.parse_variant_playlist(self.session, m3u8)

        # 3) Player-Source in Skripten?
        src = self._find_player_source_url(html)
        if src and ".m3u8" in src:
            return HLSStream.parse_variant_playlist(self.session, src)

        # 4) iframe laden und dort nochmal suchen
        iframe_url = self._find_iframe_url(html, self.url)
        if iframe_url:
            res2 = self._fetch(iframe_url)
            html2 = res2.text

            m3u8 = self._find_m3u8_in_text(html2)
            if m3u8:
                return HLSStream.parse_variant_playlist(self.session, m3u8)

            src2 = self._find_player_source_url(html2)
            if src2 and ".m3u8" in src2:
                return HLSStream.parse_variant_playlist(self.session, src2)

        # Wenn wir hier sind, haben wir nichts Öffentliches gefunden
        return None


__plugin__ = EurostarTV
