from .generic import GenericIE
from ..utils import determine_ext, unsmuggle_url


class LewdStarsIE(GenericIE):
    """LewdStars pages whose origin currently presents an invalid certificate chain."""

    IE_NAME = 'lewdstars'
    _VALID_URL = r'https?://(?:www\.)?lewdstars\.com/(?P<id>[^/?#]+)(?:/)?(?:[?#].*)?$'
    IE_DESC = 'LewdStars videos with scoped certificate handling'

    def _real_extract(self, url):
        params = self._downloader.params
        had_setting = 'nocheckcertificate' in params
        previous_setting = params.get('nocheckcertificate')
        params['nocheckcertificate'] = True
        try:
            result = super()._real_extract(url)
            if result.get('_type') == 'url_transparent' and result.get('url'):
                media_url, smuggled_data = unsmuggle_url(result['url'], {})
                referer = smuggled_data.get('referer') or url
                result.pop('_type', None)
                result.pop('ie_key', None)
                result.pop('url', None)
                result['direct'] = True
                result['formats'] = [{
                    'format_id': determine_ext(media_url, default_ext='mp4'),
                    'url': media_url,
                    'ext': determine_ext(media_url, default_ext='mp4'),
                    'http_headers': {'Referer': referer},
                }]
            return result
        finally:
            if had_setting:
                params['nocheckcertificate'] = previous_setting
            else:
                params.pop('nocheckcertificate', None)
