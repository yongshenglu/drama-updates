"""Mango TV collector.

The TV-drama channel page (https://www.mgtv.com/tv/) server-renders its cards.

    div.mgtv-card                      -> one drama
    div.mgtv-card__title[title=...]    -> drama title
    span.mgtv-card__content__duration  -> episode badge, e.g. "更新至32集"
    a.mgtv-card__link[href]            -> playback URL (playlist id)

Cast is not on the channel page; it lives in each show's detail page, which is
also server-rendered. Those are fetched concurrently after the list pass.
"""
from __future__ import annotations

import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterator

from .browser import http_get_rendered
from .http import http_get, parse_html
from .models import Drama

URL = "https://www.mgtv.com/tv/"
HEADERS = {"Referer": "https://www.mgtv.com/"}

# Cast lookups are one extra request per show; the pool keeps a full pass short.
_DETAIL_WORKERS = 8
_DETAIL_TIMEOUT = 15
_MAX_ACTORS = 4

# Format/genre labels that share the same shape as a person's name in the
# detail page payload, so they have to be excluded explicitly.
_NON_NAME = set("""微短剧 短剧 电视剧 电影 综艺 动漫 纪录片 少儿 知识 都市 古装 青春 家庭
悬疑 言情 甜宠 虐恋 喜剧 爱情 职场 历史 军旅 仙侠 武侠 奇幻 冒险 动作 犯罪 剧情 情感
现实主义 逆袭 爽剧 年下 姐弟恋 先婚后爱 契约婚姻 甜虐 虐心 治愈 成长 年代 革命 战争
谍战 权谋 宅斗 宫斗 穿越 重生 直播 美食 医疗 法律 律政 警匪 刑侦 消防 校园 都市情感
都市生活 悬疑推理 古装爱情 古装剧 民国 武侠剧 偶像 青春剧 情景喜剧 家庭伦理 都市剧
大芒短剧 大芒微剧 科幻 科幻剧 后宫 宫廷 惊悚 恐怖 战争剧 革命剧 主旋律 现实题材
""".split())

_NAME_RE = re.compile(r"^[一-龥]{2,4}$")
_NOISE_RE = re.compile(r"[0-9]|次播放|榜|分$|期$|VIP|预告|免费|更新|超前|首播|独播")


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

        # Cast is filled in a second parallel pass below.
        dramas.append(Drama(
            platform="芒果TV",
            title=title,
            episode_text=badge,
            subtitle=subtitle,
            url=urllib.parse.urljoin(URL, url) if url else "",
            has_update=bool(badge),
        ))

    # Each show's cast lives on its own detail page, so look them up in
    # parallel. A failure only loses the cast, never the platform.
    with ThreadPoolExecutor(max_workers=_DETAIL_WORKERS) as pool:
        futures = {pool.submit(_actors_for, d.url): i
                   for i, d in enumerate(dramas)}
        for fut in as_completed(futures):
            dramas[futures[fut]].actors = fut.result()

    return dramas


def _actors_for(href: str) -> list[str]:
    """Fetch a show's detail page and pull the cast out of its inline payload.

    Returns [] on any failure -- a missing cast list must never fail the
    platform, the board simply shows the drama without one.
    """
    if not href:
        return []
    detail = urllib.parse.urljoin(URL, href)
    try:
        html = http_get(detail, headers=HEADERS, timeout=_DETAIL_TIMEOUT)
    except (OSError, RuntimeError):
        # A missing cast list must never fail the platform.
        return []

    m = re.search(r"clipInfo:\{tabTitle", html)
    if not m:
        return []
    # The cast list sits in clipInfo.detail, immediately before actorUrl.
    seg = html[m.start():m.start() + 3000]
    end = seg.find("actorUrl")
    if end > 0:
        seg = seg[:end]

    names: list[str] = []
    for token in re.findall(r'font:"([^"]{1,24})"', seg):
        if _NOISE_RE.search(token) or token in _NON_NAME:
            continue
        if _NAME_RE.match(token) and token not in names:
            names.append(token)
        if len(names) >= _MAX_ACTORS:
            break
    return names


def iter_dramas() -> Iterator[Drama]:
    yield from collect()
