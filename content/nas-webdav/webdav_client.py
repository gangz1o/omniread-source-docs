"""Bounded, read-only WebDAV adapter for a configured collection."""
import base64
import hashlib
import re
import xml.etree.ElementTree as ET
from collections import deque
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

MAX_XML = 4 * 1024 * 1024
MAX_TEXT = 16 * 1024 * 1024
DAV = '{DAV:}'
PROPFIND = b'<?xml version="1.0"?><d:propfind xmlns:d="DAV:"><d:prop><d:resourcetype/></d:prop></d:propfind>'


class AdapterError(Exception):
    pass


def origin(url):
    p = urlsplit(url)
    return p.scheme.lower(), (p.hostname or '').lower(), p.port or (443 if p.scheme == 'https' else 80)


def decoded_path(path):
    value = unquote(path, encoding='utf-8', errors='strict')
    if any(part in ('.', '..') for part in value.split('/')) or any(c in value for c in ('\\', '\x00', '\r', '\n')) or re.search(r'%[0-9a-fA-F]{2}', value):
        raise AdapterError('unsafe_webdav_path')
    return value


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class WebDAV:
    def __init__(self, url, username, password, allow_http=False):
        p = urlsplit(url)
        if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password or p.query or p.fragment:
            raise AdapterError('invalid_webdav_url')
        if p.scheme != 'https' and not allow_http:
            raise AdapterError('webdav_requires_https')
        if ':' in username or not username or not password:
            raise AdapterError('invalid_webdav_credentials')
        self.root_path = decoded_path(p.path).rstrip('/') + '/'
        self.root = urlunsplit((p.scheme, p.netloc, quote(self.root_path, safe='/'), '', ''))
        self.authorization = 'Basic ' + base64.b64encode((username + ':' + password).encode()).decode()
        self.opener = build_opener(NoRedirect())

    def safe_url(self, href, parent):
        p = urlsplit(urljoin(parent, href))
        if p.username or p.password or p.query or p.fragment or origin(p.geturl()) != origin(self.root):
            raise AdapterError('unsafe_webdav_href')
        path = decoded_path(p.path)
        if path.rstrip('/') == self.root_path.rstrip('/'):
            path = self.root_path
        if not path.startswith(self.root_path):
            raise AdapterError('outside_webdav_root')
        return urlunsplit((p.scheme, p.netloc, quote(path, safe='/'), '', ''))

    def request(self, url, method, limit):
        # Only already-validated URLs may receive the NAS credential. No redirects.
        url = self.safe_url(url, self.root)
        headers = {'Authorization': self.authorization, 'Accept-Encoding': 'identity'}
        if method == 'PROPFIND':
            headers.update({'Depth': '1', 'Content-Type': 'application/xml; charset=utf-8'})
        request = Request(url, data=PROPFIND if method == 'PROPFIND' else None, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=15) as response:
                if response.status != (207 if method == 'PROPFIND' else 200):
                    raise AdapterError('unexpected_webdav_status')
                value = response.read(limit + 1)
                if len(value) > limit:
                    raise AdapterError('webdav_response_too_large')
                return value
        except HTTPError as error:
            code = error.code
            error.close()
            raise AdapterError('webdav_auth_failed' if code in (401, 403) else 'webdav_request_failed') from None
        except (URLError, OSError, ValueError):
            raise AdapterError('webdav_unavailable') from None

    def list_directory(self, url):
        raw = self.request(url, 'PROPFIND', MAX_XML)
        try:
            xml = raw.decode('utf-8-sig')
            if '\x00' in xml or '<!DOCTYPE' in xml.upper() or '<!ENTITY' in xml.upper():
                raise AdapterError('unsafe_webdav_xml')
            root = ET.fromstring(xml)
            if root.tag != DAV + 'multistatus':
                raise AdapterError('invalid_webdav_xml')
        except (UnicodeError, ET.ParseError):
            raise AdapterError('invalid_webdav_xml') from None
        parent = decoded_path(urlsplit(url).path).rstrip('/') + '/'
        entries = {}
        valid_collection = False
        for item in root.findall(DAV + 'response'):
            href = item.findtext(DAV + 'href')
            if not href:
                continue
            # Fail closed, including when a server returns an out-of-scope redirect href.
            target = self.safe_url(href, url)
            path = decoded_path(urlsplit(target).path)
            collection = None
            for status in item.findall(DAV + 'propstat'):
                if re.match(r'^HTTP/\S+ 200(?:\s|$)', status.findtext(DAV + 'status', '')):
                    resource = status.find(DAV + 'prop/' + DAV + 'resourcetype')
                    if resource is not None:
                        collection = resource.find(DAV + 'collection') is not None
            if path.rstrip('/') == parent.rstrip('/'):
                valid_collection = collection is True
                continue
            if collection is None or not path.startswith(parent):
                continue
            relative = path[len(parent):].rstrip('/')
            if not relative or '/' in relative:
                continue
            if len(relative) > 512:
                raise AdapterError('webdav_file_name_too_long')
            if collection:
                target = target.rstrip('/') + '/'
            entries[target] = (relative, collection)
        if not valid_collection:
            raise AdapterError('webdav_collection_not_confirmed')
        return [(url, name, folder) for url, (name, folder) in entries.items()]

    def scan(self):
        queue, visited, books = deque([(self.root, 0)]), set(), {}
        entry_count = 0
        while queue:
            directory, depth = queue.popleft()
            if directory in visited:
                continue
            if depth > 20 or len(visited) >= 1000:
                raise AdapterError('directory_limit_exceeded')
            visited.add(directory)
            for url, name, folder in self.list_directory(directory):
                entry_count += 1
                if entry_count > 10000:
                    raise AdapterError('entry_limit_exceeded')
                if folder:
                    queue.append((url, depth + 1))
                elif name.lower().endswith('.txt'):
                    identity = hashlib.sha256(url.encode()).hexdigest()[:24]
                    books[identity] = {'id': identity, 'title': name[:-4], 'dav_url': url}
                    if len(books) > 5000:
                        raise AdapterError('book_limit_exceeded')
        return books

    def read_text(self, url):
        data = self.request(url, 'GET', MAX_TEXT)
        codecs = ['utf-16'] if data.startswith((b'\xff\xfe', b'\xfe\xff')) else ['utf-8-sig', 'gb18030']
        for codec in codecs:
            try:
                text = data.decode(codec)
                if '\x00' in text:
                    raise AdapterError('invalid_text_file')
                return text.replace('\r\n', '\n').replace('\r', '\n')
            except UnicodeError:
                continue
        raise AdapterError('unsupported_text_encoding')


def chapters(text, limit=12000):
    """Recognize headings; bound long chapters without losing any text."""
    heading = re.compile(r'^(?:第[零〇一二三四五六七八九十百千万两\d]+[章节卷回部篇].{0,60}|chapter\s+\d+.{0,60})$', re.I)
    output, buffer, title = [], '', '正文'
    def emit(value, name):
        for offset in range(0, len(value), limit):
            suffix = '' if offset == 0 else '（续 ' + str(offset // limit + 1) + '）'
            output.append({'title': name + suffix, 'text': value[offset:offset + limit]})
            if len(output) > 10000:
                raise AdapterError('chapter_limit_exceeded')
    for line in text.splitlines(keepends=True):
        if heading.fullmatch(line.strip()):
            if buffer:
                emit(buffer, title)
            buffer, title = '', line.strip()
        buffer += line
        # Flush long non-heading sections incrementally, preserving the remainder.
        if len(buffer) > limit * 2:
            emit(buffer[:limit], title)
            buffer = buffer[limit:]
    if buffer:
        emit(buffer, title)
    return output or [{'title': '正文', 'text': ''}]
