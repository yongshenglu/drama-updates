"""iQIYI collector.

The TV-drama channel page server-renders its cards. iQIYI ships three
different card layouts on the same page (focus strip, grid, feed), but every
layout tags its semantic parts with ``data-ai-entity``, so one rule covers all
three instead of chasing hashed CSS class names:

    data-ai-entity="更新信息文案" -> episode badge, e.g. "30集全" / "限免5-7集"
    data-ai-entity="卡片标题" / "缩略图标题" / "标题" -> drama title
"""
from __future__ import annotations

import base64
import re
import urllib.parse
from typing import Iterator, Optional

from .browser import http_get_rendered
from .http import Node, http_get, parse_html
from .models import Drama

URL = "https://www.iqiyi.com/dianshiju/"
HEADERS = {"Referer": "https://www.iqiyi.com/"}

BADGE_ENTITY = "更新信息文案"
TITLE_ENTITIES = ("卡片标题", "缩略图标题", "标题")
SUBTITLE_ENTITIES = ("副标题",)

# Class substrings that mark the outermost card container.
_CARD_MARKERS = ("TilesItem", "ItemWrap", "filmFeed_filmFeed")


def _card_of(node: Node) -> Optional[Node]:
    return node.closest(
        lambda n: any(m in n.classes() for m in _CARD_MARKERS))


def _title_of(card: Node) -> str:
    el = card.find_first(lambda n: n.get("data-ai-entity") in TITLE_ENTITIES)
    return el.text_content().strip() if el else ""


def _decode_album_id(url: str) -> str:
    """Turn a redirect URL into the plain numeric album id.

    ``.../to_page_url?album_id=Mzk5...Q%3D%3D&...`` -> ``39936829436210001``
    """
    m = re.search(r"[?&]album_id=([^&]+)", url)
    if not m:
        return ""
    raw = urllib.parse.unquote(m.group(1))
    try:
        return base64.b64decode(raw + "=" * (-len(raw) % 4)).decode("ascii", "ignore").strip()
    except Exception:
        return ""


def _fetch() -> str:
    """Prefer a rendered page; fall back to plain HTTP if no browser exists."""
    browser_error = None
    try:
        html = http_get_rendered(URL, referer="https://www.iqiyi.com/")
    except Exception as exc:
        browser_error = exc
        html = http_get(URL, headers=HEADERS)
    if "data-ai-entity" not in html:
        # The shell page carries no cards; a rendered fetch is required.
        detail = f" (browser: {browser_error})" if browser_error else ""
        raise RuntimeError(f"iQIYI returned a JS shell; rendering failed{detail}")
    return html


def collect() -> list[Drama]:
    html = _fetch()
    root = parse_html(html)

    badges = root.find_all(
        lambda n: n.tag == "span" and n.get("data-ai-entity") == BADGE_ENTITY)

    dramas: list[Drama] = []
    seen: set[str] = set()
    for badge in badges:
        card = _card_of(badge)
        if card is None:
            continue
        title = _title_of(card)
        if not title:
            continue

        badge_text = badge.get("data-content").strip() or badge.text_content().strip()
        album_id = _decode_album_id(card.get("href") or _nearest_href(card))
        key = f"{title}|{badge_text}"
        if key in seen:
            continue
        seen.add(key)

        dramas.append(Drama(
            platform="爱奇艺",
            title=title,
            episode_text=badge_text,
            subtitle=_subtitle_of(card),
            url=f"https://www.iqiyi.com/a_{album_id}.html" if album_id else "",
            has_update=bool(badge_text),
        ))
    return dramas


def _subtitle_of(card: Node) -> str:
    el = card.find_first(lambda n: n.get("data-ai-entity") in SUBTITLE_ENTITIES)
    return el.text_content().strip() if el else ""


def _nearest_href(card: Node) -> str:
    """Find the card's anchor.

    Grid cards wrap their content in an <a> child, while the focus strip wraps
    the card in an <a> parent, so look in both directions.
    """
    el = card.find_first(lambda n: n.tag == "a" and n.get("href"))
    if el:
        return el.get("href")
    for anc in card.ancestors():
        if anc.tag == "a" and anc.get("href"):
            return anc.get("href")
    return ""


def iter_dramas() -> Iterator[Drama]:
    yield from collect()
