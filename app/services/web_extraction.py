import ipaddress
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx

from app.core.config import Settings
from app.services.text import normalize_text

HTML_TYPES = {"text/html", "application/xhtml+xml"}
TEXT_TYPES = {"text/plain", "text/markdown"}
SUPPORTED_WEB_TYPES = HTML_TYPES | TEXT_TYPES


@dataclass(frozen=True)
class WebPageContent:
    url: str
    title: str
    content_type: str
    text: str


async def fetch_web_page(url: str, settings: Settings) -> WebPageContent:
    normalized_url = validate_public_url(url)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }
    timeout = httpx.Timeout(settings.url_fetch_timeout_seconds)

    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout, headers=headers) as client:
        response = await client.get(normalized_url)
        _raise_for_bad_status(response)

    content_type = response.headers.get("content-type", "text/html").split(";")[0].strip().lower()
    if content_type not in SUPPORTED_WEB_TYPES:
        raise ValueError("Only HTML and plain text web pages can be indexed.")

    content = response.content
    if len(content) > settings.url_fetch_max_bytes:
        raise ValueError("Web page is too large to index.")

    text = _decode_response_text(response, content)
    if content_type in HTML_TYPES:
        title, extracted_text = extract_text_from_html(text)
    else:
        title = ""
        extracted_text = normalize_text(text)

    if not extracted_text:
        raise ValueError("No readable text found at this URL.")

    final_url = str(response.url)
    return WebPageContent(
        url=final_url,
        title=title or _fallback_title(final_url),
        content_type=content_type,
        text=extracted_text,
    )


def _raise_for_bad_status(response: httpx.Response) -> None:
    if response.status_code < 400:
        return
    if response.status_code == 403:
        raise ValueError(
            "Сайт заблокировал загрузку с сервера: 403 Forbidden. "
            "Это часто бывает у medical/news сайтов с антибот-защитой. "
            "Попробуй другую публичную страницу или сохрани текст статьи в TXT/PDF и загрузи файлом."
        )
    if response.status_code == 404:
        raise ValueError("Страница не найдена: 404 Not Found.")
    raise ValueError(f"Сайт вернул ошибку HTTP {response.status_code}.")


def validate_public_url(url: str) -> str:
    value = url.strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("URL must start with http:// or https://.")

    host = parsed.hostname
    if not host:
        raise ValueError("URL host is required.")
    if host.lower() == "localhost" or host.lower().endswith(".localhost"):
        raise ValueError("Localhost URLs are not allowed.")

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return value

    if (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
    ):
        raise ValueError("Private network URLs are not allowed.")
    return value


def extract_text_from_html(html: str) -> tuple[str, str]:
    parser = ReadableHTMLParser()
    parser.feed(html)
    parser.close()
    title = normalize_text(" ".join(parser.title_parts))
    body = normalize_text(" ".join(parser.text_parts))
    if title and not body.startswith(title):
        body = f"{title}\n\n{body}"
    return title, body


def _decode_response_text(response: httpx.Response, content: bytes) -> str:
    encoding = response.encoding or "utf-8"
    return content.decode(encoding, errors="ignore")


def _fallback_title(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if path:
        return f"{parsed.netloc}/{path}".strip("/")[:255]
    return parsed.netloc[:255]


class ReadableHTMLParser(HTMLParser):
    block_tags = {
        "article",
        "aside",
        "blockquote",
        "br",
        "dd",
        "div",
        "dl",
        "dt",
        "figcaption",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "td",
        "th",
        "tr",
        "ul",
    }
    ignored_tags = {"script", "style", "noscript", "svg", "canvas", "template"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_parts: list[str] = []
        self.title_parts: list[str] = []
        self._ignored_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        tag = tag.lower()
        if tag in self.ignored_tags:
            self._ignored_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag in self.block_tags:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.ignored_tags and self._ignored_depth > 0:
            self._ignored_depth -= 1
        elif tag == "title":
            self._in_title = False
        elif tag in self.block_tags:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text or self._ignored_depth:
            return
        if self._in_title:
            self.title_parts.append(text)
            return
        self.text_parts.append(text)
