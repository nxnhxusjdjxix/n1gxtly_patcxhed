import re

from .common import InfoExtractor
from ..utils import (
    int_or_none,
    unified_timestamp,
    urljoin,
)


class SxyPrnIE(InfoExtractor):
    """
    SxyPrn extractor that parses external host links.
    
    The site uses dual hosting:
    - Internal CDN (trafficdeposit.com) - mostly expired/deleted
    - External hosts (lulustream, doodstream, vidara, savefiles) - primary content
    
    This extractor focuses on external links which are plainly visible in HTML.
    """
    
    IE_NAME = 'sxyprn'
    _VALID_URL = r'https?://(?:www\.)?sxyprn\.com/post/(?P<id>[a-z0-9]+)\.html'
    
    _TESTS = [{
        'url': 'https://sxyprn.com/post/6a7777dae3a1e.html',
        'info_dict': {
            'id': '6a7777dae3a1e',
            'title': 'SxyPrn video 6a7777dae3a1e',
        },
        'playlist_mincount': 1,
    }]
    
    # External host patterns to extract
    _EXTERNAL_HOSTS = [
        'lulustream.com',
        'doodstream.co',
        'doodstream.com',
        'dood.to',
        'dood.watch',
        'dood.so',
        'dood.pm',
        'dood.wf',
        'dood.re',
        'vidara.so',
        'savefiles.com',
        'streamtape.com',
        'vidoza.net',
    ]
    
    def _real_extract(self, url):
        video_id = self._match_id(url)
        webpage = self._download_webpage(url, video_id)
        
        # Extract title
        title = (
            self._html_search_meta(['og:title', 'twitter:title'], webpage, default=None)
            or self._html_search_regex(
                r'<title>([^<]+)</title>',
                webpage,
                'title',
                default=f'SxyPrn video {video_id}'
            )
        )
        title = re.sub(r'\s*-\s*SXYPRN$', '', title, flags=re.IGNORECASE)
        
        # Extract metadata
        description = self._html_search_meta(
            ['og:description', 'twitter:description', 'description'],
            webpage,
            default=None
        )
        
        thumbnail = self._html_search_meta(
            ['og:image', 'twitter:image'],
            webpage,
            default=None
        )
        
        duration = self._html_search_meta('video:duration', webpage, default=None)
        duration = int_or_none(duration)
        
        upload_date = self._html_search_meta('article:published_time', webpage, default=None)
        timestamp = unified_timestamp(upload_date)
        
        # Extract external host links from HTML
        entries = []
        
        # Pattern 1: Direct iframe embeds
        for iframe in re.finditer(r'<iframe[^>]+src=["\']([^"\']+)["\']', webpage):
            iframe_url = iframe.group(1)
            if any(host in iframe_url for host in self._EXTERNAL_HOSTS):
                entries.append({
                    '_type': 'url_transparent',
                    'url': urljoin(url, iframe_url),
                    'ie_key': 'Generic',
                })
        
        # Pattern 2: Links with 'extlink' class or data attribute
        for link in re.finditer(r'<a[^>]+(?:class=["\'][^"\']*extlink[^"\']*["\']|data-extlink=["\'][^"\']*["\'])[^>]+href=["\']([^"\']+)["\']', webpage):
            link_url = link.group(1)
            if any(host in link_url for host in self._EXTERNAL_HOSTS):
                entries.append({
                    '_type': 'url_transparent',
                    'url': urljoin(url, link_url),
                    'ie_key': 'Generic',
                })
        
        return {
            '_type': 'playlist',
            'id': video_id,
            'title': title,
            'description': description,
            'thumbnail': thumbnail,
            'duration': duration,
            'timestamp': timestamp,
            'entries': entries,
        }
