"""Shared helpers: HTTP fetching and a lightweight HTML DOM parser.

The platforms render their drama lists server-side, so plain HTTP plus DOM
parsing is enough -- no headless browser needed in production.
"""
from __future__ import annotations

import gzip
import re
import urllib.error
import urllib.request
from html.parser import HTMLParser
from typing import Iterator, Optional

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip",
}


def http_get(url: str, headers: Optional[dict] = None,
             timeout: int = 20, data: Optional[bytes] = None,
             method: str = "GET") -> str:
    """Fetch a URL and return decoded text. Raises on failure."""
    hdrs = dict(DEFAULT_HEADERS)
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            charset = resp.headers.get_content_charset() or "utf-8"
            return raw.decode(charset, errors="ignore")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} for {url}") from e
    except Exception as e:
        raise RuntimeError(f"fetch failed for {url}: {e}") from e


class Node:
    """Minimal DOM node."""
    __slots__ = ("tag", "attrs", "kids", "text", "_parent")

    def __init__(self, tag: str, attrs=None):
        self.tag = tag
        self.attrs = dict(attrs or {})
        self.kids: list = []
        self.text: list[str] = []

    def own_text(self) -> str:
        return "".join(self.text).strip()

    def text_content(self) -> str:
        parts = list(self.text)
        for k in self.kids:
            if isinstance(k, Node):
                parts.append(k.text_content())
        return "".join(parts).strip()

    def get(self, key: str, default: str = "") -> str:
        return self.attrs.get(key, default) or default

    def classes(self) -> str:
        return self.get("class")

    def iter(self) -> Iterator["Node"]:
        """Yield self and all descendants."""
        yield self
        for k in self.kids:
            if isinstance(k, Node):
                yield from k.iter()

    def find_all(self, predicate) -> list["Node"]:
        return [n for n in self.iter() if predicate(n)]

    def find_first(self, predicate) -> Optional["Node"]:
        for n in self.iter():
            if predicate(n):
                return n
        return None

    def ancestors(self) -> Iterator["Node"]:
        """Walk up via the back-reference set by the parser."""
        cur = getattr(self, "_parent", None)
        while cur is not None:
            yield cur
            cur = getattr(cur, "_parent", None)

    def closest(self, predicate) -> Optional["Node"]:
        for a in self.ancestors():
            if predicate(a):
                return a
        return None


_VOID = {"img", "br", "meta", "link", "input", "hr", "source", "area", "col",
         "embed", "param", "track", "wbr", "base", "path", "circle", "rect",
         "polygon", "polyline", "line", "ellipse", "use", "stop"}


class _TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("__root__")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].kids.append(node)
        node._parent = self.stack[-1]
        if tag not in _VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].kids.append(node)
        node._parent = self.stack[-1]

    def handle_endtag(self, tag):
        # tolerate mismatched nesting by popping back to the nearest match
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        if data.strip():
            self.stack[-1].text.append(data)


def parse_html(html: str) -> Node:
    b = _TreeBuilder()
    b.feed(html)
    return b.root


def first_href(node: Node, must_contain: str = "") -> str:
    """Nearest anchor href, preferring one that contains a required token."""
    fallback = ""
    for n in node.iter():
        if n.tag == "a":
            href = n.get("href")
            if href:
                if not must_contain or must_contain in href:
                    return href
                fallback = fallback or href
    return fallback
