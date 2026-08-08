import hashlib
import time

from .common import InfoExtractor
from ..utils import ExtractorError, try_get


class GofileIE(InfoExtractor):
    """Extract media files from a GoFile public folder."""

    _VALID_URL = r'https?://(?:www\.)?gofile\.io/d/(?P<id>[^/?#]+)'
    IE_DESC = 'GoFile folders and files'
    _WEBSITE_TOKEN_SALT = '9844d94d963d30'

    def _gofile_user_agent(self):
        return (self._downloader.params.get('http_headers') or {}).get(
            'User-Agent',
            'Mozilla/5.0 (X11; Linux x86_64) '
            'AppleWebKit/537.36 Chrome/131.0 Safari/537.36')

    def _real_initialize(self):
        token_cookie = self._get_cookies('https://gofile.io/').get('accountToken')
        if token_cookie:
            self._token = token_cookie.value
            return

        response = self._download_json(
            'https://api.gofile.io/accounts', None,
            'Getting a GoFile guest account', data=b'{}',
            headers={'User-Agent': self._gofile_user_agent()})
        self._token = response['data']['token']
        self._set_cookie('.gofile.io', 'accountToken', self._token)

    def _website_token(self):
        user_agent = self._gofile_user_agent()
        period = int(time.time() / 14400)
        payload = f'{user_agent}::en-US::{self._token}::{period}::{self._WEBSITE_TOKEN_SALT}'
        return hashlib.sha256(payload.encode()).hexdigest()

    def _entries(self, folder_id):
        password = self.get_param('videopassword')
        query = {
            'contentFilter': '',
            'page': '1',
            'pageSize': '1000',
            'sortField': 'name',
            'sortDirection': '1',
        }
        if password:
            query['password'] = hashlib.sha256(password.encode()).hexdigest()

        headers = {
            'User-Agent': self._gofile_user_agent(),
            'Authorization': f'Bearer {self._token}',
            'X-Website-Token': self._website_token(),
            'X-BL': 'en-US',
        }
        response = self._download_json(
            f'https://api.gofile.io/contents/{folder_id}', folder_id,
            'Getting GoFile file list', query=query, headers=headers)
        status = response.get('status')
        if status == 'error-passwordRequired':
            raise ExtractorError(
                'This GoFile folder is password protected; use --video-password',
                expected=True)
        if status != 'ok':
            raise ExtractorError(
                f'GoFile returned status {status}', expected=True)

        children = try_get(
            response, lambda data: data['data']['children'], dict) or {}
        found_media = False
        for file_info in children.values():
            mimetype = file_info.get('mimetype') or ''
            file_type, _, file_format = mimetype.partition('/')
            if file_type not in ('video', 'audio') and file_format != 'vnd.mts':
                continue
            file_url = file_info.get('link')
            if not file_url:
                continue
            found_media = True
            yield {
                'id': file_info.get('id') or file_info.get('name'),
                'title': (file_info.get('name') or 'GoFile media').rsplit('.', 1)[0],
                'url': file_url,
                'filesize': file_info.get('size'),
                'release_timestamp': file_info.get('createTime'),
                'thumbnail': file_info.get('thumbnail'),
            }

        if not found_media:
            raise ExtractorError(
                'No video or audio files found in the GoFile folder',
                expected=True)

    def _real_extract(self, url):
        folder_id = self._match_id(url)
        return self.playlist_result(self._entries(folder_id), playlist_id=folder_id)
