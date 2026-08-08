from .common import InfoExtractor
from ..utils import (
    ExtractorError,
    traverse_obj,
)


class PornlIE(InfoExtractor):
    _VALID_URL = r'https?://(?:www\.)?pornl\.com/(?:videos?|embed)/(?P<id>\d+)'
    _WORKING = True
    IE_DESC = 'pornl.com'
    _TESTS = [{
        'url': 'https://pornl.com/videos/3901921/faye-reagan-in-stunning-faye-reagan-plays-hard-to-get-smutmerchants/',
        'info_dict': {
            'id': '3901921',
            'ext': 'mp4',
            'title': str,
            'age_limit': 18,
        },
    }]

    # Custom base64-like alphabet used by pornl.com's app.js.
    # IMPORTANT: several letters are Cyrillic look-alikes (А В С Е М), not
    # Latin — this is intentional obfuscation by the site, not a typo here.
    _ALPHABET = '\u0410\u0412\u0421D\u0415FGHIJKL\u041cNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,~'

    def _base164_decode(self, encoded):
        """Decode pornl.com's custom base164 encoding to a plain string."""
        alphabet_index = {c: i for i, c in enumerate(self._ALPHABET)}
        e = ''.join(c for c in encoded if c in alphabet_index)
        result = bytearray()
        s = 0
        while s < len(e) - 3:
            i_val = alphabet_index[e[s]]; s += 1
            o_val = alphabet_index[e[s]]; s += 1
            l_val = alphabet_index[e[s]]; s += 1
            n_val = alphabet_index[e[s]]; s += 1
            b0 = (i_val << 2) | (o_val >> 4)
            b1 = ((o_val & 15) << 4) | (l_val >> 2)
            b2 = ((l_val & 3) << 6) | n_val
            result.append(b0)
            if l_val != 64:
                result.append(b1)
            if l_val != 64 and n_val != 64:
                result.append(b2)
        return result.decode('utf-8')

    def _real_extract(self, url):
        video_id = self._match_id(url)
        page_url = f'https://pornl.com/videos/{video_id}/'
        _ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'

        # Step 1: fetch the encoded video URL from the videofile API
        data = self._download_json(
            f'https://pornl.com/api/videofile.php?video_id={video_id}&lifetime=8640000',
            video_id,
            headers={'User-Agent': _ua, 'Referer': page_url},
            note='Downloading video file info')

        if not data or not isinstance(data, list) or 'video_url' not in data[0]:
            raise ExtractorError('No video_url found in API response')

        # Prefer the entry marked is_default, else the first
        entry = next((d for d in data if d.get('is_default')), data[0])

        # Step 2: decode the custom base164 URL to /get_file/... path
        try:
            path = self._base164_decode(entry['video_url'])
        except Exception as e:
            raise ExtractorError(f'base164 decode failed: {e}') from e

        get_file_url = f'https://pornl.com{path}&download=true'

        # Step 3: follow the /get_file/ redirect chain with the tccloak=1 cookie
        # Two 302 redirects lead to the final ahcdn.com CDN URL (plain MP4).
        urlh = self._request_webpage(
            get_file_url, video_id,
            headers={
                'User-Agent': _ua,
                'Referer': page_url,
                'Cookie': 'tccloak=1',
            },
            note='Resolving CDN URL')
        direct_url = urlh.url

        if not direct_url or direct_url == get_file_url:
            raise ExtractorError('Failed to resolve CDN URL — redirect chain did not complete')

        # Step 4: fetch title/thumbnail from the metadata JSON API (best-effort)
        vid = int(video_id)
        bucket_a = (vid // 1_000_000) * 1_000_000
        bucket_b = (vid // 1_000) * 1_000
        meta = self._download_json(
            f'https://pornl.com/api/json/video/0/{bucket_a}/{bucket_b}/{vid}.json',
            video_id,
            headers={'User-Agent': _ua, 'Referer': page_url},
            note='Downloading video metadata',
            fatal=False) or {}

        video_info = traverse_obj(meta, 'video') or {}
        title = video_info.get('title') or video_id

        thumbnails = []
        for key, pref in (('thumb', 1), ('thumbsrc', 0)):
            thumb_url = video_info.get(key)
            if thumb_url:
                thumbnails.append({'url': thumb_url, 'id': key, 'preference': pref})

        ext = (entry.get('format') or '.mp4').lstrip('.')

        direct_format = {
            'format_id': 'direct',
            'url': direct_url,
            'ext': ext,
            'protocol': 'https',
            'vcodec': 'unknown',
            'acodec': 'unknown',
            'format_note': 'Direct MP4',
            'http_headers': {
                'User-Agent': _ua,
                'Referer': page_url,
            },
        }

        return {
            'id': video_id,
            'title': title,
            'url': direct_url,
            'ext': ext,
            'formats': [direct_format],
            'thumbnails': thumbnails or None,
            'age_limit': 18,
        }
