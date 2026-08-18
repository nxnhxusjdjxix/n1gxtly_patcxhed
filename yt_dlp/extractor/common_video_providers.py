import base64
import codecs
import json
import os
import re
import subprocess
import random
import time
from urllib.parse import urljoin, urlsplit
from ..dependencies import Cryptodome
from ..networking import HEADRequest, Request
from ..utils import (
    ExtractorError,
    determine_ext,
    filesize_from_tbr,
    int_or_none,
    unescapeHTML,
    url_or_none,
    parse_duration,
)

from .common import InfoExtractor


class CommonVideoProviderIE(InfoExtractor):
    """Shared provider implementations used by site and player adapters."""

    @staticmethod
    def _user_agent(downloader):
        return (downloader.params.get('http_headers') or {}).get(
            'User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) '
            'AppleWebKit/537.36 Chrome/131.0 Safari/537.36')

    @classmethod
    def _headers(cls, downloader, referer, accept='text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8'):
        return {
            'User-Agent': cls._user_agent(downloader),
            'Referer': referer,
            'Accept': accept,
        }

    @classmethod
    def _page_headers(cls, downloader, page_url):
        return cls._headers(
            downloader, page_url,
            'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8')

    def _apply_hls_format_metadata(
            self, formats, video_id, headers=None, duration=None, manifest=None):
        """Attach provider-exposed size metadata to HLS formats."""
        if duration is None and formats:
            if manifest:
                duration = self._parse_m3u8_vod_duration(manifest, video_id)
            else:
                duration = self._extract_m3u8_vod_duration(
                    formats[0].get('url'), video_id, headers=headers or {})
        for format_item in formats:
            if format_item.get('filesize') is None and format_item.get('filesize_approx') is None:
                estimated_size = filesize_from_tbr(format_item.get('tbr'), duration)
                if estimated_size is not None:
                    format_item['filesize_approx'] = estimated_size
        return duration

    def _direct_format(self, media_url, page_url, video_id, duration=None, format_id='direct'):
        """Return a direct format with request-time Content-Length metadata."""
        headers = {'Referer': page_url}
        response = self._request_webpage(
            HEADRequest(media_url), video_id, note='Checking direct media size',
            headers=headers, fatal=False)
        filesize = int_or_none(response.headers.get('Content-Length')) if response else None
        format_item = {
            'format_id': format_id,
            'url': media_url,
            'ext': determine_ext(media_url) or 'mp4',
            'http_headers': headers,
        }
        if filesize is not None:
            format_item['filesize'] = filesize
        if filesize is not None and duration:
            format_item['tbr'] = filesize * 8 / (duration * 1000)
        return format_item

    def _extract_streamtape(self, embed_url, video_id, referer):
        webpage = self._download_webpage(
            embed_url, video_id, headers=self._headers(self._downloader, referer))
        title = self._html_search_meta(
            ('og:title', 'twitter:title'), webpage, 'title', default=video_id)
        thumbnail = self._html_search_meta(
            ('og:image', 'twitter:image'), webpage, 'thumbnail', default=None)
        match = re.search(
            r"getElementById\(['\"]botlink['\"]\)\.innerHTML\s*=\s*"
            r"(?P<quote>['\"])(?P<prefix>[^'\"]+)"
            r"(?P=quote)\s*\+\s*"
            r"\((?P<quote2>['\"])(?P<value>[^'\"]+)(?P=quote2)\)"
            r"\.substring\((?P<start>\d+)\)",
            webpage)
        if not match:
            raise ExtractorError('Streamtape video URL construction not found')
        source = (
            match.group('prefix') + match.group('value')[int(match.group('start')):]
            + '&stream=1')
        source = urljoin(embed_url, source)
        duration = self._search_regex(
            r'\b(?:duration|length)\s*[:=]\s*["\']?([0-9.]+)', webpage,
            'duration', default=None)
        duration = float(duration) if duration else None
        return {
            'formats': [self._direct_format(source, embed_url, video_id, duration, 'streamtape')],
            'title': title,
            'thumbnail': url_or_none(thumbnail),
            'duration': duration,
        }

    @classmethod
    def _unpack_hanerix(cls, webpage):
        match = re.search(
            r"eval\(function\(p,a,c,k,e,d\)\{.*?\}\('(?P<p>(?:\\.|[^'])*)',"
            r'(?P<a>\d+),(?P<c>\d+),'
            r"'(?P<k>(?:\\.|[^'])*)'\.split\('\|'\)\)\)",
            webpage, re.DOTALL)
        if not match:
            raise ExtractorError('Hanerix packed player configuration not found')
        try:
            payload = codecs.decode(match.group('p'), 'unicode_escape')
            base = int(match.group('a'))
            count = int(match.group('c'))
            words = match.group('k').split('|')
        except (UnicodeDecodeError, ValueError) as exc:
            raise ExtractorError(f'Unable to read Hanerix player pack: {exc}') from exc
        for index in range(count - 1, -1, -1):
            if index < len(words) and words[index]:
                payload = re.sub(
                    rf'\b{re.escape(cls._js_base(index, base))}\b',
                    words[index], payload)
        return payload

    def _extract_hanerix(self, embed_url, video_id, referer):
        webpage = self._download_webpage(
            embed_url, video_id, headers=self._headers(self._downloader, referer))
        unpacked = self._unpack_hanerix(webpage)
        links = {}
        for name in ('hls4', 'hls3', 'hls2'):
            value = self._search_regex(
                rf'"{name}"\s*:\s*"([^"]+)"', unpacked, name,
                default=None)
            if value:
                links[name] = urljoin(embed_url, value)
        # Hanerix can expose several equivalent HLS backends.  hls4 may be
        # replaced by an ad-image playlist, while hls3 is the browser's
        # playable fallback on affected pages.  Keep the order request-time
        # and fall back when a backend is absent.
        source = next(
            (links.get(name) for name in ('hls3', 'hls2', 'hls4')
             if links.get(name)), None)
        if not source:
            raise ExtractorError('Hanerix did not expose an HLS source')
        media_headers = self._headers(self._downloader, embed_url, '*/*')
        formats, subtitles = self._extract_m3u8_formats_and_subtitles(
            source, video_id, ext='mp4', m3u8_id='hanerix',
            headers=media_headers, fatal=False)
        for format_item in formats:
            format_item.setdefault('http_headers', {}).update(media_headers)
        if not formats:
            raise ExtractorError('Hanerix HLS source returned no formats')
        duration = self._search_regex(
            r'\bduration\s*:\s*["\']?([0-9.]+)', unpacked, 'duration',
            default=None)
        duration = self._apply_hls_format_metadata(
            formats, video_id, media_headers, float(duration) if duration else None)
        thumbnail = self._search_regex(
            r'\bimage\s*:\s*["\']([^"\']+)', unpacked, 'thumbnail',
            default=None)
        return {
            'formats': formats,
            'subtitles': subtitles,
            'duration': duration,
            'thumbnail': url_or_none(thumbnail),
        }

    def _extract_hgcloud(self, embed_url, video_id, referer):
        video_id = urlsplit(embed_url).path.rstrip('/').rsplit('/', 1)[-1]
        if not re.fullmatch(r'[A-Za-z0-9_-]+', video_id):
            raise ExtractorError('HGCloud URL has no usable video ID')
        candidates = (
            f'https://hanerix.com/e/{video_id}',
            f'https://audinifer.com/e/{video_id}',
        )
        failures = []
        for candidate in candidates:
            try:
                result = self._extract_hanerix(candidate, video_id, referer)
                result['id'] = video_id
                return result
            except Exception as exc:
                failures.append(f'{candidate}: {exc}')
        raise ExtractorError('HGCloud/Hanerix extraction failed: ' + '; '.join(failures))

    def _extract_luluvdo(self, embed_url, video_id):
        # Luluvdo rejects requests that carry the source site's Referer.  The
        # provider page itself exposes a request-time HLS URL in an eval-packed
        # JWPlayer configuration, so deliberately request it without one.
        headers = {
            'User-Agent': self._user_agent(self._downloader),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        webpage = self._download_webpage(
            embed_url, video_id, headers=headers)
        unpacked = self._unpack_hanerix(webpage)
        source = self._search_regex(
            r'\bfile\s*:\s*["\'](https?[^"\']+\.m3u8[^"\']*)',
            unpacked, 'Luluvdo HLS source')
        source = unescapeHTML(source.replace(r'\/', '/'))
        formats, subtitles = self._extract_m3u8_formats_and_subtitles(
            source, video_id, ext='mp4', m3u8_id='luluvdo',
            headers=headers, fatal=False)
        if not formats:
            raise ExtractorError('Luluvdo HLS source returned no formats')
        duration = self._search_regex(
            r'\bduration\s*:\s*["\']?([0-9.]+)', unpacked, 'duration',
            default=None)
        duration = self._apply_hls_format_metadata(
            formats, video_id, headers, float(duration) if duration else None)
        thumbnail = self._search_regex(
            r'\bimage\s*:\s*["\']([^"\']+)', unpacked, 'thumbnail',
            default=None)
        return {
            'formats': formats,
            'subtitles': subtitles,
            'duration': duration,
            'thumbnail': url_or_none(thumbnail),
        }

    @staticmethod
    def _b64(value):
        if isinstance(value, bytes):
            value = value.decode()
        return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))

    @staticmethod
    def _rot13(value):
        out = []
        for char in value:
            if 'A' <= char <= 'Z':
                char = chr((ord(char) - ord('A') + 13) % 26 + ord('A'))
            elif 'a' <= char <= 'z':
                char = chr((ord(char) - ord('a') + 13) % 26 + ord('a'))
            out.append(char)
        return ''.join(out)

    @classmethod
    def _decode_voe_config(cls, encoded):
        value = cls._rot13(encoded)
        markers = ('@$', '^^', '~@', '%?', '*~', '!!', '#&')
        candidates = [value]
        for marker in markers:
            candidates = [candidate.replace(marker, '') for candidate in candidates]
        marked = value
        for marker in markers:
            marked = marked.replace(marker, '_')
        candidates.append(''.join(reversed(marked.split('_'))))
        for candidate in candidates:
            try:
                stage_one = cls._b64(candidate)
                stage_two = bytes((char - 3) & 0xff for char in stage_one)[::-1]
                config = json.loads(cls._b64(stage_two))
            except (ValueError, TypeError, json.JSONDecodeError):
                continue
            if isinstance(config, dict) and url_or_none(config.get('source')):
                return config
        raise ValueError('no valid VOE source configuration found')

    def _extract_voe_mirror(self, page_url, video_id, referer):
        webpage = self._download_webpage(
            page_url, video_id, headers=self._headers(self._downloader, referer))
        encoded = self._search_regex(
            r'<script\b[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>',
            webpage, 'VOE mirror configuration', flags=re.IGNORECASE | re.DOTALL)
        wrapper = self._parse_json(encoded, video_id)
        if isinstance(wrapper, list):
            wrapper = wrapper[0] if wrapper else None
        if not isinstance(wrapper, str):
            raise ExtractorError('VOE mirror returned an invalid configuration')
        try:
            config = self._decode_voe_config(wrapper)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise ExtractorError(f'Unable to decode VOE mirror configuration: {exc}') from exc
        source = url_or_none(config.get('source'))
        if not source:
            raise ExtractorError('VOE mirror did not expose an HLS source')
        formats, subtitles = self._extract_m3u8_formats_and_subtitles(
            source, video_id, ext='mp4', m3u8_id='voe-mirror',
            headers=self._headers(self._downloader, page_url), fatal=False)
        if not formats:
            raise ExtractorError('VOE mirror HLS source returned no formats')
        duration = self._apply_hls_format_metadata(
            formats, video_id, self._headers(self._downloader, page_url))
        return {
            'formats': formats,
            'subtitles': subtitles,
            'title': config.get('title') or video_id,
            'thumbnail': url_or_none(config.get('thumbnail')),
            'duration': duration,
        }

    def _extract_voe(self, voe_url, video_id, referer):
        # Keep the initial request fatal, matching native yt-dlp behavior.
        # In particular, let HTTP 403/429 errors reach the app's generic
        # challenge detector instead of replacing them with a provider-specific
        # "unable to resolve" error.
        result = self._download_webpage_handle(
            voe_url, video_id,
            headers=self._headers(self._downloader, referer))

        webpage, response = result
        final_url = response.url
        mirror_errors = []
        for page_url in (final_url, voe_url):
            try:
                return self._extract_voe_mirror(page_url, video_id, referer)
            except Exception as exc:
                mirror_errors.append(exc)

        if mirror_errors:
            raise mirror_errors[-1]
        raise ExtractorError('Unable to resolve VOE mirror configuration')

    def _extract_vidara(self, vidara_url, video_id, referer):
        embed_id = urlsplit(vidara_url).path.rstrip('/').rsplit('/', 1)[-1]
        stream = self._download_json(
            'https://vidara.to/api/stream', embed_id,
            'Downloading Vidara stream metadata',
            headers={
                'Content-Type': 'application/json',
                'Referer': referer,
            },
            data=json.dumps({
                'filecode': embed_id,
                'device': 'web',
            }).encode())
        media_url = stream.get('streaming_url')
        if not media_url:
            raise ExtractorError('Vidara did not return a streaming URL')
        formats = self._extract_m3u8_formats(
            media_url, video_id, ext='mp4', m3u8_id='hls',
            headers={'Referer': vidara_url}, fatal=False)
        if not formats:
            raise ExtractorError('No Vidara HLS formats found')
        duration = int_or_none(stream.get('duration') or stream.get('duration_seconds'))
        duration = self._apply_hls_format_metadata(
            formats, video_id, {'Referer': vidara_url}, duration)
        return {
            'id': video_id,
            'title': stream.get('title') or video_id,
            'thumbnail': url_or_none(stream.get('thumbnail')),
            'formats': formats,
            'duration': duration,
            'age_limit': 18,
            'http_headers': {'Referer': referer},
        }

    @staticmethod
    def _u32(value):
        return value & 0xffffffff

    @classmethod
    def _rol(cls, value, count):
        return cls._u32((value << count) | (value >> (32 - count)))

    @classmethod
    def _imul(cls, left, right):
        return cls._u32(left * right)

    @classmethod
    def _byse_digest(cls, data):
        state = [1779033703, 3144134277, 1013904242, 2773480762]

        def mix():
            state[0] = cls._u32(state[0] + state[1])
            state[3] = cls._rol(state[3] ^ state[0], 16)
            state[2] = cls._u32(state[2] + state[3])
            state[1] = cls._rol(state[1] ^ state[2], 12)
            state[0] = cls._u32(state[0] + state[1])
            state[3] = cls._rol(state[3] ^ state[0], 8)
            state[2] = cls._u32(state[2] + state[3])
            state[1] = cls._rol(state[1] ^ state[2], 7)

        for byte in data:
            state[0] = cls._rol(cls._u32(state[0] + byte), 7)
            mix()
        for _ in range(8):
            mix()
        words = []
        for _ in range(512):
            mix()
            words.append(state[0] ^ state[2])
        for _ in range(2):
            for index in range(512):
                address = words[index] & 511
                value = cls._rol(
                    cls._u32(words[index] + words[address]), 13)
                value ^= cls._imul(words[(index + 1) & 511], 2654435761)
                words[index] = cls._u32(value)
                state[0] ^= value
                mix()
        output = []
        for block in range(8):
            mix()
            value = state[0]
            for word in words[block * 64:(block + 1) * 64]:
                value = cls._u32(value + word)
                value = cls._rol(value, 5)
                value ^= cls._imul(word, 2246822519)
            output.append(cls._u32(value ^ state[2]))
        return output

    @classmethod
    def _pow_solution(cls, nonce, difficulty):
        if not nonce or not int_or_none(difficulty):
            raise ExtractorError('Byse returned an invalid proof-of-work challenge')
        helper = os.path.join(os.path.dirname(__file__), 'byse_pow')
        if not os.path.isfile(helper) or not os.access(helper, os.X_OK):
            raise ExtractorError('Byse proof-of-work helper is unavailable')
        result = subprocess.run(
            [helper, str(nonce), str(difficulty)],
            capture_output=True, text=True, timeout=180, check=False)
        if result.returncode != 0 or not result.stdout.strip().isdigit():
            raise ExtractorError(
                f'Byse proof-of-work failed: {result.stderr.strip() or "no solution"}')
        return result.stdout.strip()

    def _extract_filemoon(self, embed_url, video_id, referer):
        parsed = urlsplit(embed_url)
        api_base = f'{parsed.scheme}://{parsed.netloc}'
        embed_id = parsed.path.rstrip('/').rsplit('/', 1)[-1]
        headers = {
            **self._headers(self._downloader, referer, 'application/json, text/plain, */*'),
            'Origin': api_base,
            'X-Embed-Origin': urlsplit(referer).hostname or '',
            'X-Embed-Referer': referer,
            'X-Embed-Parent': embed_url,
            'Content-Type': 'application/json',
        }
        details = self._download_json(
            f'{api_base}/api/videos/{embed_id}/embed/details', video_id,
            headers=headers, note='Downloading Filemoon embed details',
            fatal=False) or {}
        if not details.get('embed_frame_url'):
            details = self._download_json(
                f'{api_base}/api/videos/{embed_id}/details', video_id,
                headers=headers, note='Downloading Filemoon details',
                fatal=False) or {}
        frame_url = url_or_none(details.get('embed_frame_url'))
        if not frame_url:
            raise ExtractorError(f'Filemoon record is unavailable: {embed_url}')
        frame_base = f'{urlsplit(frame_url).scheme}://{urlsplit(frame_url).netloc}'
        challenge = self._download_json(
            f'{frame_base}/api/videos/{embed_id}/embed/captcha', video_id,
            data=b'{}', headers=headers, note='Requesting Filemoon verification',
            fatal=False) or {}
        algorithm = challenge.get('algorithm')
        if algorithm and algorithm != 'sha256-leading-zero-bits':
            raise ExtractorError(f'Unsupported Filemoon proof-of-work algorithm: {algorithm}')
        solution = self._pow_solution(
            challenge.get('pow_nonce'), challenge.get('pow_difficulty'))
        verified = self._download_json(
            f'{frame_base}/api/videos/{embed_id}/embed/captcha/verify', video_id,
            data=json.dumps({
                'pow_token': challenge.get('pow_token'),
                'solution': solution,
            }).encode(), headers=headers, note='Verifying Filemoon player',
            fatal=False) or {}
        token = verified.get('token')
        if not token:
            raise ExtractorError('Filemoon verification failed')
        playback = self._download_json(
            f'{frame_base}/api/videos/{embed_id}/embed/playback', video_id,
            data=b'{"fingerprint":{}}',
            headers={**headers, 'X-Captcha-Token': token},
            note='Requesting Filemoon playback', fatal=False) or {}
        playback = playback.get('playback') or {}
        version = int_or_none(playback.get('version'))
        key_parts = playback.get('key_parts') or []
        if not (1 <= (version or 0) <= 20) or len(key_parts) < 31 - version:
            raise ExtractorError('Filemoon returned invalid playback keys')
        try:
            key = self._b64(key_parts[version - 1]) + self._b64(key_parts[30 - version])
            encrypted = self._b64(playback['payload'])
            cipher = Cryptodome.AES.new(
                key, Cryptodome.AES.MODE_GCM, nonce=self._b64(playback['iv']))
            source_data = json.loads(
                cipher.decrypt_and_verify(encrypted[:-16], encrypted[-16:]))
        except (KeyError, TypeError, ValueError) as exc:
            raise ExtractorError(f'Unable to decrypt Filemoon playback: {exc}') from exc
        formats, subtitles = [], {}
        duration = int_or_none(details.get('duration'))
        for source in source_data.get('sources') or []:
            source_url = url_or_none(source.get('url'))
            if not source_url:
                continue
            source_formats, source_subtitles = self._extract_m3u8_formats_and_subtitles(
                source_url, video_id, ext='mp4', m3u8_id='filemoon',
                headers={'User-Agent': headers['User-Agent'], 'Referer': frame_base + '/'},
                fatal=False)
            source_duration = int_or_none(source.get('duration')) or duration
            duration = self._apply_hls_format_metadata(
                source_formats, video_id,
                {'User-Agent': headers['User-Agent'], 'Referer': frame_base + '/'},
                source_duration)
            for format_info in source_formats:
                if source.get('size_bytes'):
                    format_info['filesize_approx'] = int_or_none(source['size_bytes'])
            formats.extend(source_formats)
            self._merge_subtitles(subtitles, source_subtitles)
        if not formats:
            raise ExtractorError('Filemoon returned no HLS formats')
        return {
            'formats': formats,
            'subtitles': subtitles,
            'title': details.get('title') or video_id,
            'thumbnail': url_or_none(details.get('poster_url')),
            'duration': duration,
        }

    @staticmethod
    def _js_base(value, base):
        alphabet = '0123456789abcdefghijklmnopqrstuvwxyz'
        value = int(value)
        result = ''
        while value:
            result = alphabet[value % base] + result
            value //= base
        return result or '0'

    @classmethod
    def _unpack_vidhide(cls, webpage):
        match = re.search(
            r"eval\(function\(p,a,c,k,e,d\)\{.*?\}\('(?P<p>(?:\\.|[^'])*)',"
            r'(?P<a>\d+),(?P<c>\d+),'
            r"'(?P<k>(?:\\.|[^'])*)'\.split\('\|'\)\)\)",
            webpage, re.DOTALL)
        if not match:
            raise ExtractorError('VidHide packed player configuration not found')
        try:
            payload = codecs.decode(match.group('p'), 'unicode_escape')
            words = match.group('k').split('|')
            base = int(match.group('a'))
            count = int(match.group('c'))
        except (UnicodeDecodeError, ValueError) as exc:
            raise ExtractorError(f'Unable to read VidHide player pack: {exc}') from exc
        while count:
            count -= 1
            if count < len(words) and words[count]:
                payload = re.sub(
                    rf'\b{re.escape(cls._js_base(count, base))}\b',
                    words[count], payload)
        return payload

    def _extract_vidhide(self, embed_url, video_id):
        webpage = self._download_webpage(
            embed_url, video_id, headers=self._headers(self._downloader, embed_url))
        unpacked = self._unpack_vidhide(webpage)
        links = {}
        for name in ('hls4', 'hls3', 'hls2'):
            value = self._search_regex(
                rf'"{name}"\s*:\s*"([^"]+)"', unpacked, name, default=None)
            if value:
                links[name] = unescapeHTML(value.replace(r'\/', '/'))
        source = next((links.get(name) for name in ('hls4', 'hls3', 'hls2') if links.get(name)), None)
        if not source:
            raise ExtractorError('VidHide did not expose an HLS source')
        source = urljoin(embed_url, source)
        formats, subtitles = self._extract_m3u8_formats_and_subtitles(
            source, video_id, ext='mp4', m3u8_id='vidhide',
            headers=self._headers(self._downloader, embed_url), fatal=False)
        if not formats:
            raise ExtractorError('VidHide HLS source returned no formats')
        duration = self._search_regex(
            r'\bduration\s*:\s*["\']?([0-9.]+)', unpacked, 'duration',
            default=None)
        duration = self._apply_hls_format_metadata(
            formats, video_id, self._headers(self._downloader, embed_url),
            float(duration) if duration else None)
        thumbnail = self._search_regex(
            r'\bimage\s*:\s*["\']([^"\']+)', unpacked, 'thumbnail', default=None)
        return {
            'formats': formats,
            'subtitles': subtitles,
            'duration': duration,
            'thumbnail': url_or_none(thumbnail),
        }

    def _extract_playmogo(self, url, video_id):
        """Extract Playmogo/DoodStream's request-time MP4 player source."""
        if '/e/' in url:
            embed_url = url
        else:
            embed_url = f'https://playmogo.com/e/{video_id}'
        webpage = self._download_webpage(
            embed_url, video_id,
            headers=self._headers(self._downloader, url, '*/*'))
        pass_md5_path = self._search_regex(
            r"\$\.get\(['\"](/pass_md5/[^'\"]+)['\"]",
            webpage, 'Playmogo token endpoint')
        token = self._search_regex(
            r'function\s+makePlay\s*\(\)\s*\{.*?'
            r'\?token=([^&"\']+)&expiry=',
            webpage, 'Playmogo media token', flags=re.DOTALL)
        media_base = self._download_webpage(
            urljoin(embed_url, pass_md5_path), video_id,
            headers=self._headers(self._downloader, embed_url, '*/*'),
            note='Requesting Playmogo media token').strip()
        if not media_base.startswith(('http://', 'https://')):
            raise ExtractorError('Playmogo returned an invalid media base URL')
        alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
        suffix = ''.join(random.choice(alphabet) for _ in range(10))
        media_url = (
            media_base + suffix + f'?token={token}&expiry={int(time.time() * 1000)}')
        media_headers = self._headers(self._downloader, embed_url, '*/*')
        response = self._request_webpage(
            Request(media_url, headers={**media_headers, 'Range': 'bytes=0-0'}),
            video_id, note='Checking Playmogo media metadata', fatal=False)
        filesize = None
        if response:
            content_range = response.headers.get('Content-Range') or ''
            match = re.search(r'/(\d+)$', content_range)
            filesize = int_or_none(match.group(1)) if match else int_or_none(
                response.headers.get('Content-Length'))
        title = self._html_search_meta(
            ('og:title', 'twitter:title'), webpage, 'title', default=video_id)
        if title == video_id:
            title = self._search_regex(
                r'<title[^>]*>([^<]+)</title>', webpage, 'page title',
                default=video_id)
        thumbnail = self._html_search_meta(
            ('og:image', 'twitter:image'), webpage, 'thumbnail', default=None)
        format_item = {
            'format_id': 'playmogo',
            'url': media_url,
            'ext': 'mp4',
            'http_headers': media_headers,
        }
        if filesize is not None:
            format_item['filesize'] = filesize
        return {
            'id': video_id,
            'title': title,
            'thumbnail': url_or_none(thumbnail),
            'formats': [format_item],
            'age_limit': 18,
        }



    def _extract_mixdrop(self, embed_url, video_id, referer=None):
        """Extract MixDrop progressive MP4 from packed MDCore player config."""
        headers = self._headers(
            self._downloader, referer or embed_url,
            'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8')
        webpage = self._download_webpage(
            embed_url, video_id, headers=headers)
        # MixDrop rotates hosts; follow any meta refresh / JS location if present
        unpacked = None
        try:
            unpacked = self._unpack_hanerix(webpage)
        except ExtractorError:
            # Alternate packer form used by some MixDrop mirrors
            match = re.search(
                r"eval\(function\(p,a,c,k,e,d\)\{.*?\}\('(?P<p>(?:\\.|[^'])*)',"
                r'(?P<a>\d+),(?P<c>\d+),'
                r"'(?P<k>(?:\\.|[^'])*)'\.split\('\|'\),0,\{\}\)\)",
                webpage, re.DOTALL)
            if not match:
                raise ExtractorError('MixDrop packed player configuration not found')
            try:
                payload = codecs.decode(match.group('p'), 'unicode_escape')
                base = int(match.group('a'))
                count = int(match.group('c'))
                words = match.group('k').split('|')
            except (UnicodeDecodeError, ValueError) as exc:
                raise ExtractorError(f'Unable to read MixDrop player pack: {exc}') from exc
            for index in range(count - 1, -1, -1):
                if index < len(words) and words[index]:
                    payload = re.sub(
                        rf'\b{re.escape(self._js_base(index, base))}\b',
                        words[index], payload)
            unpacked = payload

        wurl = self._search_regex(
            r'(?:MDCore\.)?wurl\s*=\s*["\']([^"\']+)["\']',
            unpacked, 'MixDrop media URL', default=None)
        if not wurl:
            wurl = self._search_regex(
                r'["\']wurl["\']\s*:\s*["\']([^"\']+)["\']',
                unpacked, 'MixDrop media URL')
        if wurl.startswith('//'):
            wurl = 'https:' + wurl
        elif wurl.startswith('/'):
            wurl = urljoin(embed_url, wurl)
        media_headers = self._headers(self._downloader, embed_url, '*/*')
        format_item = {
            'format_id': 'mixdrop',
            'url': wurl,
            'ext': determine_ext(wurl, 'mp4'),
            'http_headers': media_headers,
        }
        # Optional HEAD for filesize
        response = self._request_webpage(
            HEADRequest(wurl), video_id,
            note='Checking MixDrop media metadata', fatal=False,
            headers=media_headers)
        if response is not None:
            filesize = int_or_none(response.headers.get('Content-Length'))
            if filesize:
                format_item['filesize'] = filesize
        thumbnail = self._search_regex(
            r'(?:MDCore\.)?poster\s*=\s*["\']([^"\']+)["\']',
            unpacked, 'thumbnail', default=None)
        if thumbnail and thumbnail.startswith('//'):
            thumbnail = 'https:' + thumbnail
        title = self._html_search_meta(
            ('og:title', 'twitter:title'), webpage, 'title', default=None)
        if not title:
            title = self._search_regex(
                r'<title[^>]*>([^<]+)</title>', webpage, 'page title',
                default=video_id)
        return {
            'id': video_id,
            'title': title,
            'thumbnail': url_or_none(thumbnail),
            'formats': [format_item],
            'age_limit': 18,
        }


class StreamtapeIE(CommonVideoProviderIE):
    _VALID_URL = r'https?://(?:www\.)?streamtape\.com/e/(?P<id>[A-Za-z0-9]+)'
    _EMBED_REGEX = [r'(?P<url>https?://(?:www\.)?streamtape\.com/e/[A-Za-z0-9]+)']
    IE_DESC = 'Streamtape videos'

    def _real_extract(self, url):
        video_id = self._match_id(url)
        result = self._extract_streamtape(url, video_id, url)
        result['id'] = video_id
        result.setdefault('age_limit', 18)
        return result

class VidaraIE(CommonVideoProviderIE):
    _VALID_URL = r'https?://(?:www\.)?vidara\.to/(?:e|v)/(?P<id>[A-Za-z0-9]+)'
    _EMBED_REGEX = [r'(?P<url>https?://(?:www\.)?vidara\.to/(?:e|v)/[A-Za-z0-9]+)']
    IE_DESC = 'Vidara videos'

    def _real_extract(self, url):
        video_id = self._match_id(url)
        return self._extract_vidara(url, video_id, url)

class VoeIE(CommonVideoProviderIE):
    _VALID_URL = r'https?://(?:www\.)?voe\.sx/e/(?P<id>[A-Za-z0-9_-]+)'
    _EMBED_REGEX = [r'(?P<url>https?://(?:www\.)?voe\.sx/e/[A-Za-z0-9_-]+)']
    IE_DESC = 'VOE videos with browser-discovered mirror support'

    def _real_extract(self, url):
        video_id = self._match_id(url)
        result = self._extract_voe(url, video_id, url)
        result['id'] = video_id
        result.setdefault('age_limit', 18)
        return result

class VoeMirrorIE(CommonVideoProviderIE):
    """Explicit extractor for a mirror URL resolved from a VOE page.

    This class deliberately is not registered in yt-dlp's automatic extractor
    lookup because its URL pattern is intentionally host-agnostic. The app
    invokes it only for a URL returned by the VOE browser fallback.
    """

    _VALID_URL = r'https?://(?P<host>[^/?#]+)/(?:e|v|embed)/(?P<id>[A-Za-z0-9_-]+)'
    IE_DESC = 'VOE mirror pages using the shared player configuration'

    def _real_extract(self, url):
        video_id = self._match_id(url)
        result = self._extract_voe_mirror(url, video_id, url)
        result['id'] = video_id
        result.setdefault('age_limit', 18)
        return result

class HGCloudIE(CommonVideoProviderIE):
    _VALID_URL = r'https?://(?:www\.)?hgcloud\.to/e/(?P<id>[A-Za-z0-9_-]+)'
    _EMBED_REGEX = [r'(?P<url>https?://(?:www\.)?hgcloud\.to/e/[A-Za-z0-9_-]+)']
    IE_DESC = 'HGCloud videos through Hanerix'

    def _real_extract(self, url):
        video_id = self._match_id(url)
        result = self._extract_hgcloud(url, video_id, url)
        result.setdefault('age_limit', 18)
        return result

class LuluvdoIE(CommonVideoProviderIE):
    _VALID_URL = (
        r'https?://(?:www\.)?(?:luluvdo\.com|luluvid\.com|lulustream\.com|'
        r'luluvdoo\.com)/e/(?P<id>[A-Za-z0-9_-]+)'
    )
    _EMBED_REGEX = [
        r'(?P<url>https?://(?:www\.)?(?:luluvdo\.com|luluvid\.com|lulustream\.com|'
        r'luluvdoo\.com)/e/[A-Za-z0-9_-]+)',
    ]
    IE_DESC = 'LuluStream / Luluvdo / Luluvid videos'

    def _real_extract(self, url):
        video_id = self._match_id(url)
        result = self._extract_luluvdo(url, video_id)
        result['id'] = video_id
        result.setdefault('age_limit', 18)
        return result

class FilemoonByseIE(CommonVideoProviderIE):
    _VALID_URL = r'https?://(?:www\.)?(?:filemoon\.[^/]+|byse[^./]*\.[^/]+)/e/(?P<id>[A-Za-z0-9_-]+)'
    _EMBED_REGEX = [
        r'(?P<url>https?://(?:www\.)?(?:filemoon\.[^/]+|byse[^./]*\.[^/]+)/e/[A-Za-z0-9_-]+)',
    ]
    IE_DESC = 'Filemoon and Byse videos'

    def _real_extract(self, url):
        video_id = self._match_id(url)
        result = self._extract_filemoon(url, video_id, url)
        result['id'] = video_id
        result.setdefault('age_limit', 18)
        return result

class VidHideIE(CommonVideoProviderIE):
    _VALID_URL = r'https?://(?:www\.)?sauceplayer\.com/embed/(?P<id>[A-Za-z0-9_-]+)'
    _EMBED_REGEX = [r'(?P<url>https?://(?:www\.)?sauceplayer\.com/embed/[A-Za-z0-9_-]+)']
    IE_DESC = 'VidHide embeds served through SaucePlayer'

    def _real_extract(self, url):
        video_id = self._match_id(url)
        result = self._extract_vidhide(url, video_id)
        result['id'] = video_id
        result.setdefault('age_limit', 18)
        return result

class PlaymogoIE(CommonVideoProviderIE):
    _VALID_URL = (
        r'https?://(?:www\.)?(?:playmogo\.com|doply\.net|dood(?:stream)?\.'
        r'(?:to|watch|so|pm|wf|re|sh|ws|yt|li|la|one|tech|info|online))/'
        r'(?:d|e)/(?P<id>[A-Za-z0-9_-]+)'
    )
    _EMBED_REGEX = [
        r'(?P<url>https?://(?:www\.)?(?:playmogo\.com|doply\.net|dood(?:stream)?\.'
        r'(?:to|watch|so|pm|wf|re|sh|ws|yt|li|la|one|tech|info|online))/'
        r'(?:d|e)/[A-Za-z0-9_-]+)',
    ]
    IE_DESC = 'Playmogo / DoodStream / Doply videos'

    def _real_extract(self, url):
        video_id = self._match_id(url)
        return self._extract_playmogo(url, video_id)

class MixDropIE(CommonVideoProviderIE):
    _VALID_URL = (
        r'https?://(?:www\.)?(?:mixdrop\.(?:ag|to|co|si|bz|ch|my|club|ps)|'
        r'm[1i]xdrop\.(?:[a-z0-9]+)|mdy[a-z0-9]+\.com|miiixdrop\.net)/'
        r'[ef]/(?P<id>[A-Za-z0-9]+)'
    )
    _EMBED_REGEX = [
        r'(?P<url>https?://(?:www\.)?(?:mixdrop\.(?:ag|to|co|si|bz|ch|my|club|ps)|'
        r'm[1i]xdrop\.[a-z0-9]+|mdy[a-z0-9]+\.com|miiixdrop\.net)/'
        r'[ef]/[A-Za-z0-9]+)',
    ]
    IE_DESC = 'MixDrop videos'

    def _real_extract(self, url):
        video_id = self._match_id(url)
        # Normalize to embed path when given /f/
        if '/f/' in url:
            url = re.sub(r'/f/', '/e/', url, count=1)
        result = self._extract_mixdrop(url, video_id, url)
        result['id'] = video_id
        result.setdefault('age_limit', 18)
        return result

