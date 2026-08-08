import re

from .common import InfoExtractor
from ..utils import (
    ExtractorError,
    url_or_none,
)


class HotntubesIE(InfoExtractor):
    _VALID_URL = r'https?://(?:www\.)?hotntubes\.com/to/(?P<id>\d+)(?:-[^/?#]+)?\.html(?:[?#].*)?$'
    _WORKING = True
    IE_DESC = 'hotntubes.com'
    _TESTS = [{
        'url': 'https://hotntubes.com/to/407422-black_man_undresses_white_girl_soft.html',
        'info_dict': {
            'id': '407422',
            'ext': 'mp4',
            'title': 'Black man undresses white girl (soft)',
            'age_limit': 18,
        },
        'params': {'skip_download': 'm3u8'},
    }]

    @staticmethod
    def _find_mp4_url(webpage):
        """Find the signed MP4 URL before GenericIE mis-parses the HTML."""
        patterns = (
            # The page's canonical direct-video metadata.
            r'<link\b[^>]*\brel\s*=\s*["\']video_src["\'][^>]*\bhref\s*=\s*["\']([^"\']+\.mp4(?:\?[^"\']*)?)',
            # The old HTML5 player fallback.
            r'<source\b[^>]*\bsrc\s*=\s*["\']([^"\']+\.mp4(?:\?[^"\']*)?)',
            # Playerjs uses a quoted MP4 alternative after "or".
            r'\bor\s+(https?://[^"\'\s<>]+\.mp4(?:\?[^"\'\s<>]*)?)',
        )
        for pattern in patterns:
            match = re.search(pattern, webpage, flags=re.IGNORECASE)
            direct_url = url_or_none(match.group(1)) if match else None
            if direct_url:
                return direct_url
        return None

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(url, video_id)

        direct_url = self._find_mp4_url(webpage)
        if not direct_url:
            raise ExtractorError('Could not find a direct MP4 URL')

        title = (
            self._html_search_meta(
                ('og:title', 'twitter:title'), webpage, 'title', default=None)
            or self._html_search_regex(
                r'<title[^>]*>([^<]+)</title>', webpage, 'title', default=video_id)
        )
        title = re.sub(r'\s*\|\s*Hotntubes\.com\s*$', '', title, flags=re.IGNORECASE)

        thumbnail = self._html_search_meta(
            ('og:image', 'twitter:image'), webpage, 'thumbnail', default=None)

        direct_format = {
            'format_id': 'direct',
            'url': direct_url,
            'ext': 'mp4',
            'protocol': 'https',
            'vcodec': 'unknown',
            'acodec': 'unknown',
            'format_note': 'Direct MP4',
            'http_headers': {
                'Referer': url,
                'User-Agent': self._downloader.params.get(
                    'http_headers', {}).get('User-Agent', 'Mozilla/5.0'),
            },
        }

        return {
            'id': video_id,
            'title': title,
            'url': direct_url,
            'ext': 'mp4',
            'formats': [direct_format],
            'thumbnail': thumbnail,
            'age_limit': 18,
        }

