from .common import InfoExtractor
from ..utils import (
    int_or_none,
    parse_iso8601,
    traverse_obj,
)


class UncutXIE(InfoExtractor):
    """Uncut-X SPA extractor using the public Supabase REST API."""

    IE_NAME = 'uncutx'
    _VALID_URL = r'https?://(?:www\.)?uncut-x\.com/videos/(?P<id>[^/?#]+)'
    IE_DESC = 'Uncut-X videos via Supabase API'

    # Embedded public Supabase anonymous key from the site's JavaScript bundle
    _API_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdtbXh6eGRrbXFoaG11Z2Fwc29rIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMwNDkyMDcsImV4cCI6MjA4ODYyNTIwN30.CnycI5gQKdwoNm0Z4C8NeJV8yF3m56fAkTxIYY7MbLY'
    _API_BASE = 'https://gmmxzxdkmqhhmugapsok.supabase.co/rest/v1'

    _TESTS = [{
        'url': 'https://uncut-x.com/videos/emily-black-caryn-beaumonts-lesbian-fun',
        'info_dict': {
            'id': '2d465f75-80f0-4b12-92c3-11404deeb8ac',
            'ext': 'mp4',
            'title': 'Emily Black & Caryn Beaumont\'s Lesbian Fun',
            'thumbnail': r're:^https?://.*\.jpg$',
            'view_count': int,
            'like_count': int,
            'timestamp': int,
            'upload_date': str,
        },
        'params': {
            'skip_download': True,
        },
    }]

    def _real_extract(self, url):
        slug = self._match_id(url)

        # Query the Supabase videos table by slug
        api_url = f'{self._API_BASE}/videos'
        headers = {
            'apikey': self._API_KEY,
            'Authorization': f'Bearer {self._API_KEY}',
        }
        params = {
            'slug': f'eq.{slug}',
            'select': '*',
        }

        response = self._download_json(
            api_url, slug, headers=headers, query=params,
            note='Downloading video metadata from API')

        if not response or not isinstance(response, list) or len(response) == 0:
            raise ExtractorError(f'Video not found: {slug}', expected=True)

        video_data = response[0]

        video_id = video_data.get('id')
        video_url = video_data.get('video_url')

        if not video_url:
            raise ExtractorError('No video URL found in API response', expected=True)

        format_info = {
            'format_id': 'http-mp4',
            'url': video_url,
            'ext': 'mp4',
            'http_headers': {
                'Referer': 'https://uncut-x.com/',
            },
        }

        return {
            'id': video_id or slug,
            'title': video_data.get('title') or slug.replace('-', ' ').title(),
            'url': video_url,
            'formats': [format_info],
            'thumbnail': video_data.get('thumbnail_url'),
            'view_count': int_or_none(video_data.get('views')),
            'like_count': int_or_none(video_data.get('likes')),
            'timestamp': parse_iso8601(video_data.get('created_at')),
            'categories': traverse_obj(video_data, ('categories', ..., 'name')),
            'tags': traverse_obj(video_data, ('tags', ..., 'name')),
            'uploader': traverse_obj(video_data, ('model', 'name')),
            'uploader_id': traverse_obj(video_data, ('model', 'id')),
            'description': video_data.get('description'),
            'duration': int_or_none(video_data.get('duration')),
            'ext': 'mp4',
            'http_headers': format_info['http_headers'],
        }
