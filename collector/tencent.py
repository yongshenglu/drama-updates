"""Tencent Video collector.

Data comes from the channel page's own JSON API, which is far more stable
than scraping markup. Field mapping was confirmed against a live capture:

    params.mz_title          -> drama title
    params.episode_updated   -> "更新至33集" / "全47集"
    params.epsode_pubtime    -> "2026-10-28 20:00:01"  (note: platform typo)
    params.holly_online_time -> free-text update schedule
"""
from __future__ import annotations

import json
from typing import Iterator

from .http import USER_AGENT, http_get
from .models import Drama

API = ("https://pbaccess.video.qq.com/trpc.vector_layout.page_view.PageService/"
       "getPage?video_appid=3000010&vversion_platform=2&vdevice_guid={guid}")

HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://v.qq.com",
    "Referer": "https://v.qq.com/channel/tv",
}

# 100113 = 电视剧 (TV drama) channel
PAGE_ID = "100113"

_PAYLOAD = {
    "page_params": {
        "page_type": "channel",
        "page_id": PAGE_ID,
        "scene": "channel",
        "new_mark_label_enabled": "1",
        "vl_to_mvl": "",
    },
    "page_bypass_params": {
        "params": {
            "platform_id": "2",
            "caller_id": "3000010",
            "data_mode": "default",
            "user_mode": "default",
            "specified_strategy": "",
            "page_type": "channel",
            "page_id": PAGE_ID,
            "scene": "channel",
            "new_mark_label_enabled": "1",
        },
        "scene": "channel",
        "app_version": "",
        "abtest_bypass_id": "79d1cd60c5cdd1fa",
    },
    "page_context": None,
}

GUID = "79d1cd60c5cdd1fa"


def _walk_cards(obj, out: list) -> None:
    """Collect every params-dict that carries a cid and a title."""
    if isinstance(obj, dict):
        p = obj.get("params")
        if isinstance(p, dict) and p.get("cid") and (p.get("mz_title") or p.get("title")):
            out.append(p)
        for v in obj.values():
            _walk_cards(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk_cards(v, out)


def collect() -> list[Drama]:
    body = json.dumps(_PAYLOAD).encode("utf-8")
    url = API.format(guid=GUID)
    text = http_get(url, headers=HEADERS, data=body, method="POST")
    data = json.loads(text)

    cards: list[dict] = []
    _walk_cards(data, cards)

    # The channel page surfaces the same show twice: once as a promo/focus
    # card (often without an episode badge) and once as a normal list card.
    # Merge by cid, keeping whichever record has the most populated fields.
    by_cid: dict[str, dict] = {}
    for p in cards:
        cid = (p.get("cid") or "").strip()
        if not cid:
            continue
        prev = by_cid.get(cid)
        if prev is None or _richness(p) > _richness(prev):
            by_cid[cid] = p

    dramas: list[Drama] = []
    for cid, p in by_cid.items():
        title = (p.get("mz_title") or p.get("title") or "").strip()
        if not title:
            continue

        tags = []
        for k, v in p.items():
            if k.startswith("marklabel_") and k.endswith("_prime_text") and v:
                tags.append(str(v))

        dramas.append(Drama(
            platform="腾讯视频",
            title=title,
            episode_text=(p.get("episode_updated") or "").strip(),
            subtitle=(p.get("mz_sub_title") or p.get("stitle") or "").strip(),
            kind=(p.get("mz_type_name") or "").strip(),
            publish_time=(p.get("epsode_pubtime") or "").strip(),
            schedule=(p.get("holly_online_time") or "").strip(),
            tags=tags,
            url=f"https://v.qq.com/x/cover/{cid}.html",
            has_update=bool(p.get("episode_updated")),
        ))
    return dramas


def _richness(p: dict) -> int:
    """Score how complete a card record is, so we can keep the better copy."""
    return sum(bool(str(p.get(k) or "").strip()) for k in
               ("episode_updated", "epsode_pubtime", "holly_online_time",
                "mz_sub_title", "mz_type_name"))


def iter_dramas() -> Iterator[Drama]:
    yield from collect()
