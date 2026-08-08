import base64
import codecs
import json
import os
import re
import subprocess
from urllib.parse import urljoin, urlsplit
from .common import InfoExtractor
from ..dependencies import Cryptodome
from ..utils import (
    ExtractorError,
    int_or_none,
    unescapeHTML,
    url_or_none,
    parse_duration,
)
import hashlib
from urllib.parse import unquote, urljoin
from ..utils import (
    ExtractorError,
    determine_ext,
    int_or_none,
    unescapeHTML,
    url_or_none,
)
from ..utils import (
    ExtractorError,
    determine_ext,
    parse_duration,
)
from ..utils import (
    ExtractorError,
    traverse_obj,
)
import urllib.parse
from ..utils import (
    js_to_json,
    parse_resolution,
    urljoin,
)
from ..utils import (
    ExtractorError,
    url_or_none,
)
from urllib.parse import urljoin
from ..networking import HEADRequest
from ..utils import (
    ExtractorError,
    int_or_none,
    unescapeHTML,
)
from urllib.parse import urlsplit
from ..utils import (
    ExtractorError,
    unescapeHTML,
    url_or_none,
)

from .common_video_players import SaucePlayerIE
from .common_video_providers import CommonVideoProviderIE


class TittyTubeIE(SaucePlayerIE):
    _VALID_URL = r'https?://(?:www\.)?tittytube\.com/(?P<id>[^/?#]+)(?:/[^?#]*)?/?(?:[?#].*)?$'
    IE_DESC = 'TittyTube SaucePlayer pages'

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(
            url, video_id, headers=self._headers(self._downloader, url))
        title = (
            self._html_search_meta(('og:title', 'twitter:title'), webpage, 'title', default=None)
            or self._html_extract_title(webpage, default=video_id))
        thumbnail = self._html_search_meta('og:image', webpage, 'thumbnail', default=None)
        player_url = self._search_regex(
            r'<iframe\b[^>]*\bsrc=["\'](https?://sauceplayer\.co/e/[^"\']+)',
            webpage, 'SaucePlayer URL')
        return self._extract_sauceplayer(player_url, url, video_id, title, thumbnail)

class TheSaucelsIE(SaucePlayerIE):
    _VALID_URL = r'https?://(?:www\.)?thesauceis\.com/(?P<id>[^/?#]+)(?:/[^?#]*)?/?(?:[?#].*)?$'
    IE_DESC = 'TheSaucels SaucePlayer pages'

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(
            url, video_id, headers=self._headers(self._downloader, url))
        title = (
            self._html_search_meta(('og:title', 'twitter:title'), webpage, 'title', default=None)
            or self._html_extract_title(webpage, default=video_id))
        thumbnail = self._html_search_meta('og:image', webpage, 'thumbnail', default=None)
        player_url = self._search_regex(
            r'<iframe\b[^>]*\bsrc=["\'](https?://sauceplayer\.co/e/[^"\']+)',
            webpage, 'SaucePlayer URL')
        return self._extract_sauceplayer(player_url, url, video_id, title, thumbnail)

class XXVideosIE(CommonVideoProviderIE):
    """Extract XX Videos pages through their goofy-banana → Jessica player."""

    _VALID_URL = r'https?://(?:www\.)?xx-videos\.online/(?:[^/?#]+/)*(?P<id>\d+)(?:/[^/?#]*)?/?(?:[?#].*)?$'
    IE_DESC = 'xx-videos.online Jessica videos'

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(
            url, video_id, headers=self._page_headers(self._downloader, url))
        title = (
            self._html_search_meta(
                ('og:title', 'twitter:title'), webpage, 'title', default=None)
            or self._html_extract_title(webpage, default=video_id))
        thumbnail = self._html_search_meta(
            ('og:image', 'twitter:image'), webpage, 'thumbnail', default=None)
        player_id = self._search_regex(
            r'<iframe\b[^>]*\bsrc=["\']https?://(?:www\.)?goofy-banana\.com/e/([A-Za-z0-9_-]+)',
            webpage, 'XX Videos player ID')
        result = self._extract_jessica(
            f'https://jessicachoosemake.com/e/{player_id}', player_id, url)
        result.update({
            'id': video_id,
            'title': title or result.get('title') or video_id,
            'thumbnail': thumbnail or result.get('thumbnail'),
            'age_limit': 18,
            'http_headers': {'Referer': url},
        })
        return result

class PureLeaksIE(CommonVideoProviderIE):
    """Extract PureLeaks pages through their available provider tabs."""

    _VALID_URL = r'https?://(?:www\.)?pureleaks\.net/(?P<id>[^/?#]+?)/?(?:[?#].*)?$'
    IE_DESC = 'pureleaks.net multi-provider videos'

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(
            url, video_id, headers=self._page_headers(self._downloader, url))
        title = (
            self._html_search_meta(
                ('og:title', 'twitter:title'), webpage, 'title', default=None)
            or self._html_extract_title(webpage, default=video_id))
        thumbnail = self._html_search_meta(
            ('og:image', 'twitter:image'), webpage, 'thumbnail', default=None)
        provider_urls = re.findall(
            r'\bdata-src=["\'](https?://[^"\']+)', webpage)
        failures = []
        for provider_url in provider_urls:
            host = (urlsplit(provider_url).hostname or '').lower()
            try:
                if host.endswith('streamtape.com'):
                    result = self._extract_streamtape(provider_url, video_id, url)
                elif host.endswith('vidara.to'):
                    result = self._extract_vidara(provider_url, video_id, url)
                elif host.endswith('voe.sx'):
                    result = self._extract_voe(provider_url, video_id, url)
                elif host.endswith('luluvdo.com'):
                    result = self._extract_luluvdo(provider_url, video_id)
                elif host.endswith('hgcloud.to'):
                    result = self._extract_hgcloud(provider_url, video_id, url)
                elif 'filemoon' in host or 'byse' in host:
                    result = self._extract_filemoon(provider_url, video_id, url)
                else:
                    continue
                if not result or not result.get('formats'):
                    continue
                result.update({
                    'id': video_id,
                    'title': title or result.get('title') or video_id,
                    'thumbnail': thumbnail or result.get('thumbnail'),
                    'age_limit': 18,
                    'http_headers': {'Referer': url},
                })
                return result
            except Exception as exc:
                failures.append(f'{host}: {exc}')
        raise ExtractorError(
            f'PureLeaks {video_id}: no supported playable provider tab. '
            + ('; '.join(failures) if failures else 'no supported provider URLs found'))

class LeakPornerIE(CommonVideoProviderIE):
    """Extract LeakPorner pages through their HGCloud → Hanerix player."""

    _VALID_URL = r'https?://(?:www\.)?w\d+\.leakporner\.com/(?P<id>[^/?#]+?)/?(?:[?#].*)?$'
    IE_DESC = 'leakporner.com HGCloud/Hanerix videos'

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(
            url, video_id, headers=self._page_headers(self._downloader, url))
        title = (
            self._html_search_meta(
                ('og:title', 'twitter:title'), webpage, 'title', default=None)
            or self._html_extract_title(webpage, default=video_id))
        thumbnail = self._html_search_meta(
            ('og:image', 'twitter:image'), webpage, 'thumbnail', default=None)
        player_url = self._search_regex(
            r'data-embed=["\'](https?://(?:www\.)?hgcloud\.to/e/[^"\']+)',
            webpage, 'LeakPorner HGCloud URL')
        result = self._extract_hgcloud(player_url, video_id, url)
        result.update({
            'id': video_id,
            'title': title or video_id,
            'thumbnail': thumbnail or result.get('thumbnail'),
            'age_limit': 18,
            'http_headers': {'Referer': url},
        })
        return result

class FapticaIE(CommonVideoProviderIE):
    """Extract Faptica pages through their Voe → Jessica player."""

    _VALID_URL = r'https?://(?:www\.)?faptica\.com/video/(?P<id>\d+)(?:/[^/?#]*)?/?(?:[?#].*)?$'
    IE_DESC = 'faptica.com Voe videos'
    _TESTS = [{
        'url': 'https://faptica.com/video/2122/rachael-cavalli-stepmom-needs-something-in-her-mouth',
        'info_dict': {
            'id': '2122',
            'ext': 'mp4',
            'title': str,
            'duration': 1637,
            'age_limit': 18,
        },
        'params': {'skip_download': 'm3u8'},
    }, {
        'url': 'https://faptica.com/video/2123/gigi-dior-stepmom-wants-to-breed-on-vacation',
        'info_dict': {
            'id': '2123',
            'ext': 'mp4',
            'title': str,
            'duration': 1966,
            'age_limit': 18,
        },
        'params': {'skip_download': 'm3u8'},
    }]

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(
            url, video_id, headers=self._page_headers(self._downloader, url))
        title = (
            self._html_search_meta(
                ('og:title', 'twitter:title'), webpage, 'title', default=None)
            or self._html_extract_title(webpage, default=video_id))
        thumbnail = self._html_search_meta(
            ('og:image', 'twitter:image'), webpage, 'thumbnail', default=None)
        player_url = self._search_regex(
            r'<iframe\b[^>]*\bsrc=["\'](https?://(?:www\.)?voe\.sx/e/[^"\']+)',
            webpage, 'Faptica Voe URL')
        result = self._extract_voe(player_url, video_id, url)
        result.update({
            'id': video_id,
            'title': title,
            'thumbnail': thumbnail or result.get('thumbnail'),
            'age_limit': 18,
        })
        duration = self._search_regex(
            r'<meta\b[^>]*\bitemprop=["\']duration["\'][^>]*\bcontent=["\']([^"\']+)',
            webpage, 'duration', default=None)
        if duration:
            result['duration'] = parse_duration(duration)
        return result

class PornDudeOnlyFansBaseIE(CommonVideoProviderIE):
    """Shared helpers for individual PornDude/OnlyFans site adapters."""

    @staticmethod
    def _video_id(url):
        return url.rstrip('/').split('/')[-1].split('?', 1)[0]

    def _title(self, webpage, video_id):
        return (
            self._html_search_meta(
                ('og:title', 'twitter:title'), webpage, 'title', default=None)
            or self._html_extract_title(webpage, default=video_id)
        )

    def _extract_encoded_player(self, url, webpage, video_id):
        token = self._search_regex(
            r'player-x\.php\?q=([^"\'&\s]+)', webpage,
            'encoded player data')
        try:
            payload = base64.urlsafe_b64decode(unquote(token) + '===').decode()
            payload = unquote(payload)
            media_url = self._search_regex(
                r'<source\b[^>]*\bsrc\s*=\s*(["\'])(?P<url>.+?)\1',
                payload, 'media URL', group='url')
        except (UnicodeDecodeError, ValueError) as exc:
            raise ExtractorError(f'Unable to decode player data: {exc}') from exc
        thumbnail = self._html_search_meta(
            'og:image', webpage, 'thumbnail', default=None)
        if determine_ext(media_url) == 'm3u8' or re.search(r'\.m3u8(?:[?#]|$)', media_url):
            headers = {'Referer': url}
            formats, subtitles = self._extract_m3u8_formats_and_subtitles(
                media_url, video_id, ext='mp4', m3u8_id='fapnut',
                headers=headers, fatal=False)
            if not formats:
                raise ExtractorError('Encoded player HLS source returned no formats')
            duration = self._apply_hls_format_metadata(formats, video_id, headers)
            return {
                'id': video_id,
                'title': self._title(webpage, video_id),
                'formats': formats,
                'subtitles': subtitles,
                'duration': duration,
                'thumbnail': thumbnail,
                'age_limit': 18,
                'http_headers': headers,
            }
        return {
            'id': video_id,
            'title': self._title(webpage, video_id),
            'formats': [self._direct_format(media_url, url, video_id)],
            'thumbnail': thumbnail,
            'age_limit': 18,
        }

class NSFW247IE(PornDudeOnlyFansBaseIE):
    """Extract NSFW247 pages that expose a direct HTML5 MP4 source."""

    _VALID_URL = r'https?://(?:www\.)?nsfw247\.to/(?P<id>[^/?#]+?)/?(?:[?#].*)?$'
    IE_DESC = 'nsfw247.to direct HTML5 videos'

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(
            url, video_id, headers=self._page_headers(self._downloader, url))
        media_url = self._search_regex(
            r'<source\b[^>]*\bsrc\s*=\s*(["\'])(?P<url>[^"\']+?\.mp4(?:[?#][^"\']*)?)\1',
            webpage, 'NSFW247 MP4 source', group='url')
        title = (
            self._html_search_meta(('og:title', 'twitter:title'), webpage, 'title', default=None)
            or self._html_extract_title(webpage, default=video_id))
        thumbnail = self._html_search_meta(
            ('og:image', 'twitter:image'), webpage, 'thumbnail', default=None)
        return {
            'id': video_id,
            'title': title,
            'formats': [self._direct_format(media_url, url, video_id)],
            'thumbnail': thumbnail,
            'age_limit': 18,
            'http_headers': {'Referer': url},
        }

class GoonityIE(PornDudeOnlyFansBaseIE):
    """Extract Goonity pages from their JSON-LD direct MP4 metadata."""

    _VALID_URL = r'https?://(?:www\.)?goonity\.com/(?:(?:[a-z]{2})/)?(?P<model>[^/?#]+)/videos/(?P<id>\d+)(?:[/?#].*)?$'
    IE_DESC = 'goonity.com direct MP4 videos'

    @staticmethod
    def _json_ld_nodes(webpage):
        for block in re.findall(
                r'<script\b[^>]*\btype=["\']application/ld\+json["\'][^>]*>(?P<json>.*?)</script>',
                webpage, flags=re.IGNORECASE | re.DOTALL):
            try:
                data = json.loads(block)
            except (TypeError, ValueError):
                continue
            if isinstance(data, list):
                yield from data
            elif isinstance(data, dict) and isinstance(data.get('@graph'), list):
                yield from data['@graph']
            elif isinstance(data, dict):
                yield data

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(
            url, video_id, headers=self._page_headers(self._downloader, url))
        metadata = next((
            node for node in self._json_ld_nodes(webpage)
            if isinstance(node, dict) and url_or_none(node.get('contentUrl'))
        ), {})
        media_url = url_or_none(metadata.get('contentUrl'))
        if not media_url:
            raise ExtractorError('Goonity direct MP4 URL was not found')
        title = (
            metadata.get('name')
            or self._html_search_meta(('og:title', 'twitter:title'), webpage, 'title', default=None)
            or self._html_extract_title(webpage, default=video_id))
        thumbnail = metadata.get('thumbnailUrl')
        if isinstance(thumbnail, (list, tuple)):
            thumbnail = next((url_or_none(item) for item in thumbnail), None)
        else:
            thumbnail = url_or_none(thumbnail)
        thumbnail = (
            thumbnail
            or self._html_search_meta(('og:image', 'twitter:image'), webpage, 'thumbnail', default=None))
        result = {
            'id': video_id,
            'title': title,
            'formats': [self._direct_format(media_url, url, video_id, parse_duration(metadata.get('duration')))],
            'thumbnail': thumbnail,
            'duration': parse_duration(metadata.get('duration')),
            'width': int_or_none(metadata.get('width')),
            'height': int_or_none(metadata.get('height')),
            'age_limit': 18,
            'http_headers': {'Referer': url},
        }
        return result

    def _extract_vidara_page(self, url, webpage, video_id):
        embed_url = self._search_regex(
            r'https?://vidara\.to/e/(?P<id>[A-Za-z0-9]+)',
            webpage, 'Vidara embed URL', group=0)
        result = self._extract_vidara(embed_url, video_id, url)
        result.update({
            'id': video_id,
            'title': self._title(webpage, video_id),
            'thumbnail': self._html_search_meta(
                'og:image', webpage, 'thumbnail', default=None) or result.get('thumbnail'),
            'age_limit': 18,
            'http_headers': {'Referer': url},
        })
        return result

class OnlyJerkIE(PornDudeOnlyFansBaseIE):
    _VALID_URL = r'https?://(?:www\.)?onlyjerk\.net/(?!videos/?(?:[?#]|$))(?P<id>[^/?#]+)'
    IE_DESC = 'onlyjerk.net Vidara videos'

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(url, video_id)
        return self._extract_vidara_page(url, webpage, video_id)

class HornySimpIE(PornDudeOnlyFansBaseIE):
    _VALID_URL = r'https?://(?:www\.)?hornysimp\.com/(?P<id>[^/?#]+)'
    IE_DESC = 'hornysimp.com Vidara videos'

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(url, video_id)
        return self._extract_vidara_page(url, webpage, video_id)

class BornToBeFuckIE(PornDudeOnlyFansBaseIE):
    _VALID_URL = r'https?://(?:www\.)?borntobefuck\.com/watch/(?P<id>\d+)'
    IE_DESC = 'borntobefuck.com videos'

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(url, video_id)
        player_url = f'https://borntobefuck.com/videos/{video_id}/player?lang=en'
        player_page = self._download_webpage(player_url, video_id)
        media_url = self._search_regex(
            r'<video\b[^>]*\bdata-hls-url\s*=\s*(["\'])(?P<url>.+?)\1',
            player_page, 'BornToBeFuck HLS URL', group='url')
        thumbnail = self._search_regex(
            r'<video\b[^>]*\bdata-(?:poster|thumb)\s*=\s*(["\'])(?P<url>.+?)\1',
            player_page, 'thumbnail', group='url', default=None)
        formats = self._extract_m3u8_formats(
            media_url, video_id, ext='mp4', m3u8_id='hls',
            headers={'Referer': player_url}, fatal=False)
        if not formats:
            raise ExtractorError('No BornToBeFuck HLS formats found')
        duration = self._apply_hls_format_metadata(
            formats, video_id, {'Referer': player_url})
        return {
            'id': video_id,
            'title': self._title(webpage, video_id),
            'thumbnail': thumbnail or self._html_search_meta(
                'og:image', webpage, 'thumbnail', default=None),
            'formats': formats,
            'duration': duration,
            'age_limit': 18,
            'http_headers': {'Referer': player_url},
        }

class HotLeakIE(PornDudeOnlyFansBaseIE):
    _VALID_URL = r'https?://(?:www\.)?hotleak\.vip/(?P<model>[^/?#]+)/video/(?P<id>\d+)'
    IE_DESC = 'hotleak.vip videos'

    @staticmethod
    def _decode_hotleak_token(token):
        if not token or len(token) <= 32:
            raise ExtractorError('Invalid HotLeak media token')
        try:
            media_url = base64.b64decode(token[16:-16][::-1]).decode()
        except (ValueError, UnicodeDecodeError) as exc:
            raise ExtractorError(f'Unable to decode HotLeak media token: {exc}') from exc
        if not re.match(r'https?://', media_url):
            raise ExtractorError('HotLeak media token did not contain a URL')
        return media_url

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(url, video_id)
        raw_video = self._search_regex(
            r'data-video\s*=\s*(["\'])(?P<data>.+?)\1',
            webpage, 'HotLeak video data', group='data')
        try:
            video_data = json.loads(unescapeHTML(raw_video))
            media_url = self._decode_hotleak_token(video_data['source'][0]['src'])
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ExtractorError(f'Invalid HotLeak video data: {exc}') from exc
        manifest = self._download_webpage(media_url, video_id, fatal=False)
        formats, _ = self._parse_m3u8_formats_and_subtitles(
            manifest, media_url, 'mp4', m3u8_id='hls',
            fatal=False)
        if not formats:
            raise ExtractorError('No HotLeak HLS formats found')
        for format_ in formats:
            format_.pop('http_headers', None)
            format_['no_headers'] = True
            format_['hls_media_playlist_data'] = manifest
        duration = self._apply_hls_format_metadata(
            formats, video_id, manifest=manifest)
        return {
            'id': video_id,
            'title': video_data.get('attributes', {}).get('title') or self._title(webpage, video_id),
            'thumbnail': video_data.get('attributes', {}).get('poster'),
            'formats': formats,
            'duration': duration,
            'age_limit': 18,
        }

class ThotFlixIE(PornDudeOnlyFansBaseIE):
    _VALID_URL = r'https?://(?:www\.)?thotflix\.com/(?P<id>[^/?#]+)'
    IE_DESC = 'thotflix.com videos'

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(url, video_id)
        media_url = self._search_regex(
            r'<video\b[^>]*\bdata-cfp-src\s*=\s*(["\'])(?P<url>.+?)\1',
            webpage, 'ThotFlix media URL', group='url')
        thumbnail = self._search_regex(
            r'<video\b[^>]*\bdata-cfp-poster\s*=\s*(["\'])(?P<url>.+?)\1',
            webpage, 'thumbnail', group='url', default=None)
        return {
            'id': video_id,
            'title': self._title(webpage, video_id),
            'thumbnail': thumbnail,
            'formats': [self._direct_format(media_url, url, video_id)],
            'age_limit': 18,
            'http_headers': {'Referer': url},
        }

class RealPornClipIE(PornDudeOnlyFansBaseIE):
    _VALID_URL = r'https?://(?:www\.)?realpornclip\.com/(?P<id>[^/?#]+)'
    IE_DESC = 'realpornclip.com videos'

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(url, video_id)
        return self._extract_encoded_player(url, webpage, video_id)

class FapNutIE(PornDudeOnlyFansBaseIE):
    _VALID_URL = r'https?://(?:www\.)?fapnut\.net/(?P<id>[^/?#]+)'
    IE_DESC = 'fapnut.net videos'

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(url, video_id)
        return self._extract_encoded_player(url, webpage, video_id)

class ThotChicksIE(CommonVideoProviderIE):
    """Extract ThotChicks pages through their ThotPlay AES/HLS player."""

    _VALID_URL = r'https?://(?:www\.)?thotchicks\.com/(?P<id>[^/?#]+?)/?(?:[?#].*)?$'
    IE_DESC = 'thotchicks.com ThotPlay videos'
    _TESTS = [{
        'url': 'https://thotchicks.com/barbellinaa-strips-naked-and-gives-hot-joi-onlyfans-video-leaked/',
        'info_dict': {
            'id': 'barbellinaa-strips-naked-and-gives-hot-joi-onlyfans-video-leaked',
            'ext': 'mp4',
            'title': str,
            'age_limit': 18,
        },
        'params': {'skip_download': 'm3u8'},
    }]

    @staticmethod
    def _cryptojs_decrypt(value, passphrase):
        """Decrypt CryptoJS AES passphrase ciphertext using OpenSSL KDF."""
        encrypted = base64.b64decode(value)
        if encrypted[:8] != b'Salted__':
            raise ValueError('missing CryptoJS salt')
        salt = encrypted[8:16]
        ciphertext = encrypted[16:]
        derived = b''
        previous = b''
        while len(derived) < 48:
            previous = hashlib.md5(previous + passphrase.encode() + salt).digest()
            derived += previous
        cipher = Cryptodome.AES.new(
            derived[:32], Cryptodome.AES.MODE_CBC, iv=derived[32:48])
        plaintext = cipher.decrypt(ciphertext)
        padding = plaintext[-1]
        if not 1 <= padding <= 16 or plaintext[-padding:] != bytes([padding]) * padding:
            raise ValueError('invalid AES padding')
        return plaintext[:-padding].decode()

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(url, video_id)
        title = (
            self._html_search_meta(('og:title', 'twitter:title'), webpage, 'title', default=None)
            or self._html_extract_title(webpage, default=video_id))
        thumbnail = self._html_search_meta(
            ('og:image', 'twitter:image'), webpage, 'thumbnail', default=None)
        player_url = self._search_regex(
            r'<iframe\b[^>]*\bsrc=["\'](https?://(?:www\.)?thotplay\.com/e/[^"\']+)',
            webpage, 'ThotPlay URL')
        player_page = self._download_webpage(
            player_url, video_id, headers={'Referer': url})
        encrypted = self._search_regex(
            r'\b(?:const|let|var)\s+videoURL\s*=\s*["\']([^"\']+)',
            player_page, 'ThotPlay encrypted video URL')
        key = self._search_regex(
            r'decryptLink\(\s*videoURL\s*,\s*["\']([^"\']+)',
            player_page, 'ThotPlay decryption key')
        try:
            source = url_or_none(self._cryptojs_decrypt(encrypted, key))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ExtractorError(f'Unable to decrypt ThotPlay source: {exc}') from exc
        if not source:
            raise ExtractorError('ThotPlay did not expose an HLS source')
        formats, subtitles = self._extract_m3u8_formats_and_subtitles(
            source, video_id, ext='mp4', m3u8_id='thotplay',
            headers={'Referer': player_url}, fatal=False)
        if not formats:
            raise ExtractorError('ThotPlay HLS source returned no formats')
        duration = self._apply_hls_format_metadata(
            formats, video_id, {'Referer': player_url})
        return {
            'id': video_id,
            'title': title,
            'thumbnail': thumbnail,
            'formats': formats,
            'subtitles': subtitles,
            'duration': duration,
            'age_limit': 18,
            'http_headers': {'Referer': url},
        }

class ThotsterIE(CommonVideoProviderIE):
    """Extract the requested Thotster post's direct CDN media entry."""

    _VALID_URL = r'https?://(?:www\.)?thotster\.com/post/(?P<id>[^/?#]+?)/?(?:[?#].*)?$'
    IE_DESC = 'thotster.com post media'
    _TESTS = [{
        'url': 'https://thotster.com/post/alinity-listen-up-fuckbois-someone-leaked-my-naughty-pop-000643',
        'info_dict': {
            'id': 'alinity-listen-up-fuckbois-someone-leaked-my-naughty-pop-000643',
            'ext': 'mp4',
            'title': str,
            'age_limit': 18,
        },
    }]

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(url, video_id)
        title = (
            self._html_search_meta(('og:title', 'twitter:title'), webpage, 'title', default=None)
            or self._html_extract_title(webpage, default=video_id))
        marker = webpage.find('initialPosts')
        post_html = webpage[:marker] if marker >= 0 else webpage
        media = re.search(
            r'\\?"mediaItem\\?"\s*:\s*\{\s*\\?"type\\?"\s*:\s*\\?"video\\?"\s*,\s*'
            r'\\?"url\\?"\s*:\s*\\?"(?P<url>https?://[^"\\]+)'
            r'(?:\\?"\s*,\s*\\?"thumbnail\\?"\s*:\s*\\?"(?P<thumbnail>[^"\\]+))?',
            post_html)
        if not media:
            raise ExtractorError('Thotster requested post did not expose a video media entry')
        media_url = unescapeHTML(media.group('url')).replace(r'\u0026', '&')
        if not url_or_none(media_url) or 'cdn.thotster.net/' not in media_url:
            raise ExtractorError('Thotster media entry is not a first-party CDN URL')
        thumbnail = media.group('thumbnail')
        return {
            'id': video_id,
            'title': title,
            'thumbnail': url_or_none(unescapeHTML(thumbnail)) if thumbnail else None,
            'formats': [self._direct_format(
                media_url, url, video_id, format_id='source')],
            'age_limit': 18,
            'http_headers': {'Referer': url},
        }

class OnlyChicksHubIE(CommonVideoProviderIE):
    """Extract OnlyChicksHub's official API-backed MP4 route."""

    _VALID_URL = r'https?://(?:www\.)?onlychickshub\.com/video/(?P<id>\d+)(?:-[^/?#]*)?/?(?:[?#].*)?$'
    IE_DESC = 'onlychickshub.com official videos'
    _TESTS = [{
        'url': 'https://onlychickshub.com/video/4655-mia-malkova-joi-for-gooners-poker-table-tease-with-big-boobs-fishnet',
        'info_dict': {
            'id': '4655',
            'ext': 'mp4',
            'title': 'Mia Malkova JOI for Gooners – Poker Table Tease with Big Boobs & Fishnet',
            'duration': 486,
            'thumbnail': r're:^https?://',
            'age_limit': 18,
        },
        'params': {'skip_download': True},
    }]

    def _real_extract(self, url):
        video_id = self._match_id(url)
        api_url = f'https://api.onlychickshub.com/videos/{video_id}'
        record = self._download_json(
            api_url, video_id, 'Downloading OnlyChicksHub video metadata',
            headers={'Referer': url}) or {}
        item = record.get('item') if isinstance(record, dict) else None
        if not isinstance(item, dict):
            raise ExtractorError('OnlyChicksHub returned no video record')
        content_path = item.get('content_url')
        if not isinstance(content_path, str) or not content_path:
            raise ExtractorError('OnlyChicksHub did not expose an official video URL')
        content_url = urljoin('https://onlychickshub.com/', content_path)
        return {
            'id': video_id,
            'title': item.get('title') or video_id,
            'thumbnail': url_or_none(item.get('thumb')),
            'duration': int_or_none(item.get('duration_seconds')),
            'formats': [self._direct_format(
                content_url, url, video_id,
                duration=int_or_none(item.get('duration_seconds')),
                format_id='official')],
            'age_limit': 18,
            'http_headers': {'Referer': url},
        }

class HornyLeakIE(CommonVideoProviderIE):
    """Extract HornyLeak's dynamic HDPlayer HLS source."""

    _VALID_URL = r'https?://(?:www\.)?hornyleak\.tv/video/(?P<id>\d+)(?:/[^/?#]*)?/?(?:[?#].*)?$'
    IE_DESC = 'hornyleak.tv HDPlayer videos'
    _TESTS = [{
        'url': 'https://www.hornyleak.tv/video/32294/stepsister-comatozze-asking-permission-to-go-party/',
        'info_dict': {
            'id': '32294',
            'ext': 'mp4',
            'title': str,
            'thumbnail': r're:^https?://',
            'age_limit': 18,
        },
        'params': {'skip_download': 'm3u8'},
    }]

    def _real_extract(self, url):
        video_id = self._match_id(url)
        page_url = url
        webpage = self._download_webpage(url, video_id, fatal=False)
        if not webpage:
            # The public page can be retired while its first-party embed
            # remains active and playable.
            page_url = f'https://www.hornyleak.tv/embed/{video_id}/'
            webpage = self._download_webpage(page_url, video_id)
        title = (
            self._html_search_meta(('og:title', 'twitter:title'), webpage, 'title', default=None)
            or self._html_extract_title(webpage, default=video_id))
        thumbnail = self._html_search_meta(
            ('og:image', 'twitter:image'), webpage, 'thumbnail', default=None)
        first_embed = self._search_regex(
            r'<iframe\b[^>]*\bsrc=["\'](https?://(?:www\.)?hornyleak\.tv/embed/\d+/?[^"\']*)',
            webpage, 'HornyLeak embed URL', default=None)
        if first_embed:
            embed_page = self._download_webpage(
                first_embed, video_id, headers={'Referer': page_url})
        else:
            first_embed = page_url
            embed_page = webpage
        provider_url = self._search_regex(
            r'<iframe\b[^>]*\bsrc=["\'](https?://hdplayer\.gives/embed/[^"\']+)',
            embed_page, 'HDPlayer URL')
        provider_page = self._download_webpage(
            provider_url, video_id, headers={'Referer': first_embed})
        encoded_source = self._search_regex(
            r'\bfile\s*:\s*["\'](https?://hdplayer\.gives/list/[^"\']+)',
            provider_page, 'HDPlayer HLS source')
        source = urljoin(provider_url, encoded_source)
        master = self._download_webpage(
            source, video_id, note='Downloading HDPlayer master playlist',
            headers={'Referer': provider_url, 'Accept': '*/*'})
        media_headers = {'Referer': provider_url, 'Accept': '*/*'}
        formats, subtitles = self._parse_m3u8_formats_and_subtitles(
            master, source, ext='mp4', entry_protocol='m3u8',
            m3u8_id='hdplayer',
            headers=media_headers, video_id=video_id)
        for format_item in formats:
            format_item.setdefault('http_headers', {}).update(media_headers)
        if not formats:
            raise ExtractorError('HDPlayer HLS source returned no formats')
        duration = self._apply_hls_format_metadata(
            formats, video_id, media_headers)
        for format_item in formats:
            format_item.setdefault('downloader_options', {})['ffmpeg_args'] = ['-f', 'hls']
        return {
            'id': video_id,
            'title': title,
            'thumbnail': thumbnail,
            'formats': formats,
            'subtitles': subtitles,
            'duration': duration,
            'age_limit': 18,
            'http_headers': {'Referer': page_url},
        }

class OnlyPornIE(CommonVideoProviderIE):
    """Extract OnlyPorn's page-provided, base-164 encoded MP4 sources."""

    _VALID_URL = r'https?://(?:www\.)?onlyporn\.tube/video/(?P<id>\d+)(?:/[^/?#]*)?/?(?:[?#].*)?$'
    IE_DESC = 'onlyporn.tube'
    _ALPHABET = 'АВСDЕFGHIJKLМNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,~'
    _TESTS = [{
        'url': 'https://www.onlyporn.tube/video/10247701/best-xxx-movie-teen-18-hot-watch-it/',
        'info_dict': {
            'id': '10247701',
            'ext': 'mp4',
            'title': str,
            'duration': 853,
            'thumbnail': r're:^https?://',
            'age_limit': 18,
        },
        'params': {'skip_download': True},
    }, {
        'url': 'https://www.onlyporn.tube/video/10244331/horny-xxx-clip-latin-woman-unbelievable-will-enslaves-your-mind-gracie-bon-and-gracie-parker/',
        'info_dict': {
            'id': '10244331',
            'ext': 'mp4',
            'title': str,
            'duration': 570,
            'thumbnail': r're:^https?://',
            'age_limit': 18,
        },
        'params': {'skip_download': True},
    }]

    def _base164_decode(self, encoded):
        alphabet_index = {char: index for index, char in enumerate(self._ALPHABET)}
        encoded = ''.join(char for char in encoded if char in alphabet_index)
        result = bytearray()
        for offset in range(0, len(encoded), 4):
            values = [alphabet_index.get(char, 0) for char in encoded[offset:offset + 4]]
            if len(values) < 4:
                break
            first, second, third, fourth = values
            result.append((first << 2) | (second >> 4))
            if third != 64:
                result.append(((second & 15) << 4) | (third >> 2))
            if fourth != 64:
                result.append(((third & 3) << 6) | fourth)
        return unquote(result.decode('latin-1'))

    def _title(self, webpage, video_id):
        return (
            self._search_regex(
                r'vpage_data\s*=\s*\{.*?\bvit\s*:\s*["\'](?P<title>[^"\']+)',
                webpage, 'title', group='title', flags=re.DOTALL, default=None)
            or self._html_search_meta(
                ('og:title', 'twitter:title'), webpage, 'title', default=None)
            or self._html_extract_title(webpage, default=video_id)
        )

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(url, video_id)
        encoded_sources = self._search_regex(
            r'initPlayer\(\{.*?hlsEnableDuration\s*:\s*\d+.*?,\s*'
            r'(?P<sources>["\'])(?P<data>.+?)(?P=sources)\s*,\s*\[',
            webpage, 'encoded source list', group='data', flags=re.DOTALL)
        try:
            sources = json.loads(self._base164_decode(encoded_sources))
        except (TypeError, ValueError, UnicodeDecodeError) as exc:
            raise ExtractorError(f'Unable to decode OnlyPorn sources: {exc}') from exc
        if not isinstance(sources, list):
            raise ExtractorError('OnlyPorn source list has an unexpected shape')

        page_title = self._title(webpage, video_id)
        thumbnail = self._html_search_meta(
            ('og:image', 'twitter:image'), webpage, 'thumbnail', default=None)
        duration = parse_duration(self._search_regex(
            r'vpage_data\s*=\s*\{.*?\bduration\s*:\s*["\'](?P<duration>[^"\']+)',
            webpage, 'duration', group='duration', flags=re.DOTALL, default=None))
        formats = []
        for source in sources:
            if not isinstance(source, dict) or not source.get('video_url'):
                continue
            source_url = self._base164_decode(source['video_url'])
            if not source_url.startswith(('http://', 'https://')):
                source_url = urljoin(url, source_url)
            format_id = re.sub(r'\.mp4$', '', source.get('format') or 'direct')
            format_item = self._direct_format(
                source_url, url, video_id, duration=duration, format_id=format_id)
            format_item['format_note'] = format_id.upper()
            formats.append(format_item)
        if not formats:
            raise ExtractorError('OnlyPorn did not expose any playable sources')
        return {
            'id': video_id,
            'title': page_title,
            'thumbnail': thumbnail,
            'duration': duration,
            'formats': formats,
            'age_limit': 18,
            'http_headers': {'Referer': url},
        }

class FappTimeIE(CommonVideoProviderIE):
    """Extract the confirmed FappTime Voe/Jessica and Filemoon/Byse paths."""

    _VALID_URL = r'https?://(?:www\.)?fapptime\.com/(?P<id>[^/?#]+?)/?(?:[?#].*)?$'
    _JESSICA_BASE_URL = 'https://jessicachoosemake.com/e/'
    IE_DESC = 'fapptime.com'
    _TESTS = [{
        'url': 'https://fapptime.com/comatozze-as-venom-masturbates-with-a-dildo/',
        'info_dict': {
            'id': 'comatozze-as-venom-masturbates-with-a-dildo',
            'ext': 'mp4',
            'title': str,
            'age_limit': 18,
        },
        'params': {'skip_download': 'm3u8'},
    }]


    @staticmethod
    def _players(webpage):
        players = []
        seen = set()
        for match in re.finditer(r'<iframe\b(?P<attrs>[^>]+)>', webpage, re.I):
            attrs = match.group('attrs')
            name = (re.search(
                r'\btitle\s*=\s*["\']([^"\']+)["\']', attrs, re.I) or
                re.search(r'\baria-label\s*=\s*["\']([^"\']+)["\']', attrs, re.I))
            name = unescapeHTML(name.group(1)).strip() if name else 'Unknown player'
            url_match = re.search(
                r'\bdata-lazy-src\s*=\s*["\']([^"\']+)["\']', attrs, re.I)
            url_match = url_match or re.search(
                r'\bsrc\s*=\s*["\']([^"\']+)["\']', attrs, re.I)
            player_url = url_or_none(unescapeHTML(url_match.group(1))) if url_match else None
            if not player_url or player_url in ('about:blank',) or player_url in seen:
                continue
            seen.add(player_url)
            players.append({'name': name, 'url': player_url})
        return players

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(
            url, video_id, headers=self._page_headers(self._downloader, url))
        title = (
            self._html_search_meta(('og:title', 'twitter:title'), webpage, 'title', default=None)
            or self._html_extract_title(webpage, default=video_id))
        title = re.sub(r'\s*[-|]\s*Fapptime\s*$', '', title, flags=re.IGNORECASE).strip()
        thumbnail = self._html_search_meta(
            ('og:image', 'twitter:image'), webpage, 'thumbnail', default=None)
        failures = []
        supported_player_found = False
        for player in self._players(webpage):
            player_url = player['url']
            host = (urlsplit(player_url).hostname or '').lower()
            try:
                if 'voe.' in host or host.endswith('voe.sx'):
                    supported_player_found = True
                    result = self._extract_voe(player_url, video_id, url)
                elif 'filemoon' in host or 'byse' in host:
                    supported_player_found = True
                    result = self._extract_filemoon(player_url, video_id, url)
                else:
                    continue
                if result and result.get('formats'):
                    result.setdefault('id', video_id)
                    result['title'] = title
                    result.setdefault('thumbnail', thumbnail)
                    result.setdefault('age_limit', 18)
                    return result
                raise ExtractorError('no formats returned')
            except Exception as exc:
                failures.append(f'{player["name"]} ({player_url}): {exc}')
        if not self._players(webpage):
            raise ExtractorError(
                f'FappTime {video_id}: no player iframes were found')
        if not supported_player_found:
            raise ExtractorError(
                f'FappTime {video_id}: no supported Voe or Filemoon/Byse player was found')
        raise ExtractorError(
            f'FappTime {video_id}: no playable source found. Attempts: '
            + '; '.join(failures))

class ShareNudeIE(CommonVideoProviderIE):
    """Extract ShareNude pages through their Source 1/2 provider buttons."""

    _VALID_URL = r'https?://(?:www\.)?share-nude\.com/v/(?P<display_id>[^/?#]+)/(?P<id>\d+)(?:[/?#].*)?$'
    IE_DESC = 'share-nude.com provider-switcher pages'

    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(
            url, video_id, headers=self._page_headers(self._downloader, url))
        title = (
            self._html_search_meta(('og:title', 'twitter:title'), webpage, 'title', default=None)
            or self._html_extract_title(webpage, default=video_id))
        thumbnail = self._html_search_meta(
            ('og:image', 'twitter:image'), webpage, 'thumbnail', default=None)
        provider_urls = re.findall(
            r'\bdata-src=["\'](https?://[^"\']+)', webpage)
        og_provider = self._html_search_meta(
            'og:video:url', webpage, 'provider URL', default=None)
        if og_provider and og_provider not in provider_urls:
            provider_urls.insert(0, og_provider)
        failures = []
        for provider_url in provider_urls:
            provider_url = unescapeHTML(provider_url)
            host = (urlsplit(provider_url).hostname or '').lower()
            try:
                if host.endswith('streamtape.com'):
                    result = self._extract_streamtape(provider_url, video_id, url)
                elif host.endswith('voe.sx'):
                    result = self._extract_voe(provider_url, video_id, url)
                else:
                    continue
                if not result or not result.get('formats'):
                    continue
                result.update({
                    'id': video_id,
                    'title': title or result.get('title') or video_id,
                    'thumbnail': thumbnail or result.get('thumbnail'),
                    'age_limit': 18,
                    'http_headers': {'Referer': url},
                })
                return result
            except Exception as exc:
                failures.append(f'{host}: {exc}')
        raise ExtractorError(
            f'ShareNude {video_id}: no supported playable source. '
            + ('; '.join(failures) if failures else 'no Streamtape or Voe source found'))
