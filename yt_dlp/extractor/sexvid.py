import re
import urllib.parse

from .common import InfoExtractor
from ..utils import (
    js_to_json,
    parse_resolution,
    urljoin,
)


class SexvidIE(InfoExtractor):
    # Covers both sexvid.xxx and sexvid1.com (identical KVS platform, different domains)
    _VALID_URL = r'https?://(?:www\.)?sexvid(?:1\.com|\.xxx)/(?P<id>[a-z0-9][a-z0-9-]*[a-z0-9])\.html'
    _TESTS = [{
        'url': 'https://www.sexvid.xxx/hot-video-with-the-busty-arabian-porn-slut-mia-khalifa.html',
        'info_dict': {
            'id': '92390',
            'display_id': 'hot-video-with-the-busty-arabian-porn-slut-mia-khalifa',
            'ext': 'mp4',
            'title': str,
            'thumbnail': r're:https?://cdn\d+\.sexvid\.xxx/.+\.jpg',
            'age_limit': 18,
        },
    }, {
        'url': 'https://www.sexvid1.com/hot-video-with-the-busty-arabian-porn-slut-mia-khalifa.html',
        'info_dict': {
            'id': '92390',
            'display_id': 'hot-video-with-the-busty-arabian-porn-slut-mia-khalifa',
            'ext': 'mp4',
            'title': str,
            'thumbnail': r're:https?://cdn\d+\.sexvid1\.com/.+\.jpg',
            'age_limit': 18,
        },
    }]

    # ── KVS URL-decoding helpers (from GenericIE._kvs_*) ─────────────────────
    @staticmethod
    def _kvs_get_license_token(license_code):
        license_code = license_code.replace('$', '')
        license_values = [int(char) for char in license_code]
        modlicense = license_code.replace('0', '1')
        center = len(modlicense) // 2
        fronthalf = int(modlicense[:center + 1])
        backhalf = int(modlicense[center:])
        modlicense = str(4 * abs(fronthalf - backhalf))[:center + 1]
        return [
            (license_values[index + offset] + current) % 10
            for index, current in enumerate(map(int, modlicense))
            for offset in range(4)
        ]

    @classmethod
    def _kvs_get_real_url(cls, video_url, license_code):
        """Decode a KVS function/0/... URL into a direct download URL."""
        if not video_url.startswith('function/0/'):
            return video_url
        parsed = urllib.parse.urlparse(video_url[len('function/0/'):])
        license_token = cls._kvs_get_license_token(license_code)
        urlparts = parsed.path.split('/')
        HASH_LENGTH = 32
        hash_ = urlparts[3][:HASH_LENGTH]
        indices = list(range(HASH_LENGTH))
        accum = 0
        for src in reversed(range(HASH_LENGTH)):
            accum += license_token[src]
            dest = (src + accum) % HASH_LENGTH
            indices[src], indices[dest] = indices[dest], indices[src]
        urlparts[3] = ''.join(hash_[index] for index in indices) + urlparts[3][HASH_LENGTH:]
        return urllib.parse.urlunparse(parsed._replace(path='/'.join(urlparts)))

    # ── Flashvars extraction ──────────────────────────────────────────────────
    @staticmethod
    def _extract_flashvars_block(webpage):
        """
        Extract the var flashvars = {...} JS object using brace counting so that
        curly braces inside string values (e.g. {time} in timeline URLs) are
        handled correctly.  Returns the raw JS object string including the outer
        braces, or None if not found.
        """
        m = re.search(r'var\s+flashvars\s*=\s*(\{)', webpage)
        if not m:
            return None
        start = m.start(1)
        depth, in_str, i = 0, None, start
        while i < len(webpage):
            c = webpage[i]
            if in_str:
                if c == '\\':
                    i += 2
                    continue
                if c == in_str:
                    in_str = None
            elif c in ('"', "'"):
                in_str = c
            elif c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return webpage[start:i + 1]
            i += 1
        return None

    def _real_extract(self, url):
        display_id = self._match_id(url)
        webpage = self._download_webpage(url, display_id)

        raw_flashvars = self._extract_flashvars_block(webpage)
        if not raw_flashvars:
            raise self.raise_no_formats(
                'Could not find player flashvars', expected=True, video_id=display_id)

        # Strip adv_ keys — they often contain JS string-concatenation expressions
        # (e.g.  adv_pre_vast: '/url?' + current_keyword) that are not valid JSON.
        clean = re.sub(r'(?<!-)\badv_\w+\s*:[^\n}]+', '', raw_flashvars)
        flashvars = self._parse_json(clean, display_id, transform_source=js_to_json)

        video_id = flashvars['video_id']
        license_code = flashvars['license_code']

        # Collect all video_url / video_alt_url* keys
        url_keys = sorted(k for k in flashvars if re.match(r'^video_(?:url|alt_url\d*)$', k))
        formats = []
        for key in url_keys:
            raw_url = flashvars[key]
            if '/get_file/' not in raw_url:
                continue
            real_url = urljoin(url, self._kvs_get_real_url(raw_url, license_code))
            format_id = flashvars.get(f'{key}_text', key)
            formats.append({
                'url': real_url,
                'format_id': format_id,
                'ext': 'mp4',
                **(parse_resolution(format_id) or parse_resolution(raw_url)),
                'http_headers': {'Referer': url},
            })

        if not formats:
            self.raise_no_formats('No downloadable video formats found', video_id=display_id)

        title = (
            self._html_search_regex(r'<h1[^>]*>(.+?)</h1>', webpage, 'title', default=None)
            or self._html_search_meta(['og:title', 'twitter:title'], webpage, 'title',
                                      default=display_id)
        )

        return {
            'id': video_id,
            'display_id': display_id,
            'title': title,
            'thumbnail': urljoin(url, flashvars.get('preview_url')),
            'formats': formats,
            'age_limit': 18,
        }
