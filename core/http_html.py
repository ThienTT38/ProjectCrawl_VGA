"""
HTTP client and HTML parsing utilities supporting httpx + BeautifulSoup4 when installed,
with a built-in Python standard-library DOM tree parser fallback (`html.parser` + `urllib.request`).
"""

from __future__ import annotations

import asyncio
import json
import re
import urllib.request
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional

try:
    import httpx

    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

try:
    from bs4 import BeautifulSoup

    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


DEFAULT_HEADERS: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
}


class DOMNode:
    """Unified DOM node abstraction wrapping either BeautifulSoup Tag or stdlib HTML tree."""

    def __init__(
        self,
        tag: str,
        attrs: Dict[str, str],
        children: Optional[List["DOMNode"]] = None,
        text_parts: Optional[List[str]] = None,
    ):
        self.tag = tag.lower()
        self.attrs = attrs
        self.children: List[DOMNode] = children or []
        self.text_parts: List[str] = text_parts or []

    @property
    def classes(self) -> List[str]:
        raw = self.attrs.get("class", "")
        return [c.strip() for c in raw.split() if c.strip()]

    def get_text(self, separator: str = " ", strip: bool = True) -> str:
        parts: List[str] = []
        self._collect_text(parts)
        joined = separator.join(parts)
        if strip:
            joined = re.sub(r"\s+", " ", joined).strip()
        return joined

    def _collect_text(self, acc: List[str]) -> None:
        for t in self.text_parts:
            if t.strip():
                acc.append(t.strip())
        for child in self.children:
            child._collect_text(acc)

    def attr(self, name: str, default: str = "") -> str:
        return self.attrs.get(name, default)

    def matches(
        self,
        tag: Optional[str] = None,
        class_name: Optional[str] = None,
        attr_filters: Optional[Dict[str, str]] = None,
    ) -> bool:
        if tag and self.tag != tag.lower():
            return False
        if class_name and class_name not in self.classes:
            return False
        if attr_filters:
            for k, v in attr_filters.items():
                if self.attrs.get(k) != v:
                    return False
        return True

    def find_all(
        self,
        tag: Optional[str] = None,
        class_name: Optional[str] = None,
        attr_filters: Optional[Dict[str, str]] = None,
    ) -> List["DOMNode"]:
        results: List[DOMNode] = []
        for child in self.children:
            if child.matches(tag=tag, class_name=class_name, attr_filters=attr_filters):
                results.append(child)
            results.extend(
                child.find_all(tag=tag, class_name=class_name, attr_filters=attr_filters)
            )
        return results

    def find_first(
        self,
        tag: Optional[str] = None,
        class_name: Optional[str] = None,
        attr_filters: Optional[Dict[str, str]] = None,
    ) -> Optional["DOMNode"]:
        for child in self.children:
            if child.matches(tag=tag, class_name=class_name, attr_filters=attr_filters):
                return child
            found = child.find_first(tag=tag, class_name=class_name, attr_filters=attr_filters)
            if found is not None:
                return found
        return None


VOID_ELEMENTS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


class _StdlibDOMBuilder(HTMLParser):
    """Builds a lightweight DOMNode tree using Python's built-in HTMLParser."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = DOMNode("document", {})
        self.stack: List[DOMNode] = [self.root]

    def handle_starttag(self, tag: str, attrs: List[tuple[str, Optional[str]]]) -> None:
        attr_dict = {k.lower(): (v if v is not None else "") for k, v in attrs}
        node = DOMNode(tag=tag, attrs=attr_dict)
        self.stack[-1].children.append(node)
        if tag.lower() not in VOID_ELEMENTS:
            self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: List[tuple[str, Optional[str]]]) -> None:
        attr_dict = {k.lower(): (v if v is not None else "") for k, v in attrs}
        node = DOMNode(tag=tag, attrs=attr_dict)
        self.stack[-1].children.append(node)

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        for idx in range(len(self.stack) - 1, 0, -1):
            if self.stack[idx].tag == t:
                del self.stack[idx:]
                break

    def handle_data(self, data: str) -> None:
        if self.stack:
            self.stack[-1].text_parts.append(data)


def parse_html_tree(html_text: str) -> DOMNode:
    """Parse HTML string into a unified DOMNode tree."""
    builder = _StdlibDOMBuilder()
    builder.feed(html_text)
    return builder.root


async def fetch_url_text(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 20.0,
) -> str:
    """Fetch URL text asynchronously via httpx if available, else urllib in thread executor."""
    merged_headers = {**DEFAULT_HEADERS, **(headers or {})}
    if HAS_HTTPX:
        async with httpx.AsyncClient(
            headers=merged_headers,
            timeout=timeout,
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.text

    def _sync_fetch() -> str:
        req = urllib.request.Request(url, headers=merged_headers, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")

    return await asyncio.to_thread(_sync_fetch)
