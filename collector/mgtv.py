"""Mango TV collector.

The TV-drama channel page (https://www.mgtv.com/tv/) server-renders its cards.

    div.mgtv-card                      -> one drama
    div.mgtv-card__title[title=...]    -> drama title
    span.mgtv-card__content__duration  -> episode badge, e.g. "更新至32集"
    a.mgtv-card__link[href]            -> playback URL (playlist id)
    div.c-title-container              -> section heading preceding the cards

Cards appear in a different visual flavour on this page (a large lead card
beside a 2x2 grid) but share the same classes, so one pass covers both.
"""
from __future__ import annotations

import re
import urllib.parse
from typing import Iterator

from .browser import http_get_rendered
from .http import http_get, parse_html
from .models import Drama

URL = "https://www.mgtv.com/tv/"
HEADERS = {"Referer": "https://www.mgtv.com/"}

# Short-drama blocks are not what this board is for.
_SKIP_SECTIONS = ("精品短剧", "短剧")


def _fetch() -> str:
    """Prefer a rendered page; fall back to plain HTTP if no browser exists."""
    try:
        html = http_get_rendered(URL, referer="https://www.mgtv.com/",
                                 settle=9, scrolls=4)
    except Exception:
        html = http_get(URL, headers=HEADERS)
    if "mgtv-card" not in html:
        raise RuntimeError("Mango TV returned a JS shell; browser rendering unavailable")
    return html


def collect() -> list[Drama]:
    html = _fetch()
    root = parse_html(html)

    cards = root.find_all(lambda n: "mgtv-card" in n.classes()
                          and "mgtv-card__" not in n.classes())

    dramas: list[Drama] = []
    seen: set[str] = set()
    for card in cards:
        title_el = card.find_first(lambda n: "mgtv-card__title" in n.classes())
        title = (title_el.get("title") or title_el.text_content()).strip() if title_el else ""
        if not title:
            continue

        dur = card.find_first(lambda n: "mgtv-card__content__duration" in n.classes())
        badge = dur.text_content().strip() if dur else ""

        link = card.find_first(lambda n: n.tag == "a" and n.get("href"))
        url = link.get("href") if link else ""

        desc_el = card.find_first(lambda n: "mgtv-card__description" in n.classes())
        subtitle = (desc_el.get("title") or desc_el.text_content()).strip() if desc_el else ""

        key = f"{title}|{badge}"
        if key in seen:
            continue
        seen.add(key)

        dramas.append(Drama(
            platform="芒果TV",
            title=title,
            episode_text=badge,
            subtitle=subtitle,
            url=urllib.parse.urljoin(URL, url) if url else "",
            has_update=bool(badge),
        ))
    return dramas


def iter_dramas() -> Iterator[Drama]:
    yield from collect()
