import base64
import json
import re
from urllib.parse import urljoin

from .common import InfoExtractor
from ..networking import HEADRequest
from ..utils import (
    ExtractorError,
    int_or_none,
    unescapeHTML,
)


class ThotPornIE(InfoExtractor):
    _VALID_URL = r'https?://(?:www\.)?thotporn\.tv/(?P<model>[a-z0-9][a-z0-9_-]*)(?:/(?P<section>video)(?:/(?P<id>\d+))?)?/?(?:[?#].*)?$'
    IE_DESC = 'thotporn.tv'
    _TESTS = [{
        'url': 'https://thotporn.tv/mackzjoness/video/10734188',
        'info_dict': {
            'id': '10734188',
            'ext': 'mp4',
            'title': str,
            'thumbnail': r're:https?://.+',
            'age_limit': 18,
        },
    }, {
        'url': 'https://thotporn.tv/mackzjoness/video',
        'info_dict': {
            'id': 'mackzjoness',
            '_type': 'playlist',
            'title': str,
            'playlist_count': int,
        },
    }]

    @staticmethod
    def _attribute(tag, name):
        match = re.search(
            rf'\b{name}\s*=\s*(?P<quote>["\'])(?P<value>.*?)(?P=quote)',
            tag, flags=re.IGNORECASE | re.DOTALL)
        return unescapeHTML(match.group('value')) if match else None

    @classmethod
    def _video_cards(cls, webpage):
        card_pattern = (
            r'(?is)<div\b'
            r'(?=[^>]*\bclass\s*=\s*["\'][^"\']*\blight-gallery-item\b)'
            r'[^>]*>')
        for match in re.finditer(card_pattern, webpage):
            tag = match.group(0)
            data_url = cls._attribute(tag, 'data-url')
            raw_video = cls._attribute(tag, 'data-video')
            if not data_url or not raw_video:
                continue
            try:
                video_data = json.loads(raw_video)
            except (TypeError, ValueError):
                continue
            source = (video_data.get('source') or [{}])[0]
            encoded_url = source.get('src') if isinstance(source, dict) else None
            if not encoded_url:
                continue
            id_match = re.search(r'/video/(\d+)', data_url)
            yield {
                'id': cls._attribute(tag, 'data-title') or (id_match.group(1) if id_match else None),
                'url': data_url,
                'title': cls._attribute(tag, 'data-title'),
                'thumbnail': cls._attribute(tag, 'data-thumb'),
                'resolution': cls._attribute(tag, 'data-lg-size'),
                'video_data': video_data,
                'encoded_url': encoded_url,
            }

    @staticmethod
    def _decode_media_url(encoded_url):
        """Decode ThotPorn's 16-character wrapper around a reversed Base64 URL."""
        if not encoded_url or len(encoded_url) <= 32:
            raise ExtractorError('Invalid ThotPorn media token')
        try:
            decoded = base64.b64decode(encoded_url[16:-16][::-1]).decode('utf-8')
        except (ValueError, UnicodeDecodeError) as exc:
            raise ExtractorError(f'Unable to decode ThotPorn media token: {exc}') from exc
        if not re.match(r'https?://', decoded):
            raise ExtractorError('ThotPorn media token did not contain a URL')
        return decoded

    def _estimate_hls_size(self, manifest, manifest_url, page_url, video_id):
        segment_urls = [
            urljoin(manifest_url, line.strip())
            for line in (manifest or '').splitlines()
            if line.strip() and not line.lstrip().startswith('#')
        ]
        if not segment_urls:
            return None

        segment_sizes = []
        for segment_url in segment_urls:
            response = self._request_webpage(
                HEADRequest(segment_url), video_id,
                headers={'Referer': page_url},
                note='Checking HLS segment size', fatal=False)
            segment_size = int_or_none(
                response.headers.get('Content-Length')) if response else None
            if segment_size is None:
                return None
            segment_sizes.append(segment_size)
        return sum(segment_sizes)

    def _extract_video(self, card, webpage, page_url, video_id):
        media_url = self._decode_media_url(card['encoded_url'])
        manifest = self._download_webpage(media_url, video_id, fatal=False)
        formats, _ = self._parse_m3u8_formats_and_subtitles(
            manifest, media_url, 'mp4', m3u8_id='hls',
            fatal=False)
        if not formats:
            raise ExtractorError('No downloadable HLS formats found', video_id=video_id)
        for format_ in formats:
            format_.pop('http_headers', None)
            format_['no_headers'] = True
            format_['hls_media_playlist_data'] = manifest
        duration = self._parse_m3u8_vod_duration(manifest or '', video_id)
        manifest_cache = {media_url: manifest}
        size_cache = {}
        for format_ in formats:
            format_manifest_url = format_.get('url') or media_url
            if format_manifest_url not in manifest_cache:
                manifest_cache[format_manifest_url] = self._download_webpage(
                    format_manifest_url, video_id, fatal=False)
            if format_manifest_url not in size_cache:
                size_cache[format_manifest_url] = self._estimate_hls_size(
                    manifest_cache[format_manifest_url], format_manifest_url,
                    page_url, video_id)
            filesize = size_cache[format_manifest_url]
            if filesize is not None:
                format_['filesize_approx'] = filesize
                if duration:
                    format_['tbr'] = filesize * 8 / duration / 1000
        resolution_match = re.match(r'(?P<width>\d+)-(?P<height>\d+)', card.get('resolution') or '')
        if resolution_match:
            resolution = {
                'width': int(resolution_match.group('width')),
                'height': int(resolution_match.group('height')),
            }
            for format_ in formats:
                format_.update(resolution)
        else:
            resolution = {}

        title = (
            self._html_search_meta(
                ('og:title', 'twitter:title'), webpage, 'title', default=None)
            or self._html_extract_title(webpage, default=card.get('title') or video_id)
        )
        poster = (card.get('video_data') or {}).get('attributes', {}).get('poster')
        return {
            'id': video_id,
            'display_id': card.get('title') or video_id,
            'title': title,
            'thumbnail': card.get('thumbnail') or poster,
            'url': media_url,
            'ext': 'mp4',
            'formats': formats,
            **resolution,
            'duration': duration,
            'age_limit': 18,
        }

    def _real_extract(self, url):
        match = self._match_valid_url(url)
        model = match.group('model')
        video_id = match.group('id')
        webpage = self._download_webpage(url, video_id or model)
        cards = list(self._video_cards(webpage))

        if video_id:
            card = next((card for card in cards if card.get('id') == video_id), None)
            if not card:
                raise ExtractorError(
                    f'Could not find video {video_id} in the ThotPorn page')
            return self._extract_video(card, webpage, url, video_id)

        entries = []
        seen_ids = set()
        for card in cards:
            entry_id = card.get('id')
            if not entry_id or entry_id in seen_ids:
                continue
            seen_ids.add(entry_id)
            entry_url = urljoin(url, card['url'])
            entries.append(self.url_result(
                entry_url, ThotPornIE, entry_id,
                title=card.get('title') or entry_id,
                thumbnail=card.get('thumbnail')))

        if not entries:
            raise ExtractorError('No ThotPorn video entries found')
        playlist_title = (
            self._html_search_meta(
                ('og:title', 'twitter:title'), webpage, 'title', default=None)
            or f'{model} videos'
        )
        return self.playlist_result(
            entries, playlist_id=model, playlist_title=playlist_title)
