import base64
import codecs
import json
import os
import re
import subprocess
from urllib.parse import urljoin, urlsplit
from ..dependencies import Cryptodome
from ..utils import (
    ExtractorError,
    int_or_none,
    unescapeHTML,
    url_or_none,
    parse_duration,
)

from .common_video_providers import CommonVideoProviderIE


class CommonVideoPlayerIE(CommonVideoProviderIE):
    """Shared player discovery and provider dispatch."""

    def _extract_sauceplayer(self, player_url, page_url, video_id, title=None, thumbnail=None):
        webpage = self._download_webpage(
            player_url, video_id, headers=self._headers(self._downloader, page_url))
        encoded = self._search_regex(
            r'(?:let|var)\s+dataLink\s*=\s*(\{.*?\});',
            webpage, 'SaucePlayer source configuration',
            flags=re.DOTALL)
        data = self._parse_json(encoded, video_id)
        embeds = (data.get('data') or {}).get('embeds') or []
        tokens = [entry.get('link') for entry in embeds if entry.get('link')]
        decrypted = self._download_json(
            'https://sauceplayer.co/api/decrypt', video_id,
            data=json.dumps({'links': tokens}).encode(),
            headers=self._headers(
                self._downloader, player_url,
                'application/json, text/plain, */*') | {'Content-Type': 'application/json'},
            note='Decrypting SaucePlayer sources') or {}
        links = decrypted.get('links') or []
        failures = []
        for position, entry in enumerate(embeds):
            decoded = next(
                (item.get('link') for item in links
                 if int_or_none(item.get('index')) == position), None)
            if not decoded and position < len(links):
                decoded = links[position].get('link')
            if not decoded:
                continue
            host = (urlsplit(decoded).hostname or '').lower()
            provider = (entry.get('servername') or '').lower()
            try:
                if host.endswith('voe.sx') or provider == 'voe':
                    result = self._extract_voe(decoded, video_id, page_url)
                elif 'byse' in host or 'filemoon' in host or provider == 'filemoon':
                    result = self._extract_filemoon(decoded, video_id, page_url)
                elif provider == 'vidhide' or (
                        host == 'sauceplayer.com' and '/embed/' in urlsplit(decoded).path):
                    result = self._extract_vidhide(decoded, video_id)
                else:
                    continue
                if result and result.get('formats'):
                    result['id'] = video_id
                    result['title'] = title or result.get('title') or video_id
                    result['thumbnail'] = thumbnail or result.get('thumbnail')
                    result.setdefault('age_limit', 18)
                    return result
            except Exception as exc:
                failures.append(f'{provider or host}: {exc}')
        raise ExtractorError(
            f'SaucePlayer {video_id}: no supported playable source. '
            + ('; '.join(failures) if failures else 'all sources were unavailable'))

class SaucePlayerIE(CommonVideoPlayerIE):
    """Extract SaucePlayer pages and dispatch their decrypted providers."""

    _VALID_URL = r'https?://(?:www\.)?sauceplayer\.co/e/(?P<id>[A-Za-z0-9_-]+)'
    IE_DESC = 'SaucePlayer multi-source embeds'

    def _real_extract(self, url):
        video_id = self._match_id(url)
        return self._extract_sauceplayer(url, url, video_id)
