"""Youku collector.

The TV-drama channel page (https://www.youku.com/ku/webtv) server-renders its
full item list into ``window.__INITIAL_DATA__``. Parsing that JSON is far more
reliable than matching CSS class hashes.

    item.title       -> drama title
    item.lbTexts     -> episode badge, e.g. "30集全" / "限免11-12集"
    item.updateTips  -> "有更新" when Youku flags a recent update
    item.mark.text   -> corner badge, e.g. "独播" / "VIP" / "限免中"
    item.action_value-> show id used to build the playback URL
"""
from __future__ import annotations

import json
import re
from typing import Iterator

from .http import http_get
from .models import Drama

URL = "https://www.youku.com/ku/webtv"
HEADERS = {"Referer": "https://www.youku.com/"}

_ASSIGN = re.compile(r"window\.__INITIAL_DATA__\s*=")
_JS_LITERALS = re.compile(r"\b(undefined|NaN|Infinity)\b")

# Corner badges that are not part of the episode count.
_NON_EPISODE_MARKS = {"广告", "预告", "预告片"}


def _extract_json(html: str) -> str:
    m = _ASSIGN.search(html)
    if not m:
        raise ValueError("Youku __INITIAL_DATA__ not found in page")
    blob = html[m.end():]
    end = blob.find("</script>")
    if end > 0:
        blob = blob[:end]
    return _JS_LITERALS.sub("null", blob).rstrip().rstrip(";").strip()


def _walk_items(obj, out: list) -> None:
    if isinstance(obj, dict):
        lst = obj.get("itemList")
        if isinstance(lst, list):
            out.extend(x for x in lst if isinstance(x, dict))
        for v in obj.values():
            _walk_items(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk_items(v, out)


def collect() -> list[Drama]:
    html = http_get(URL, headers=HEADERS)
    data = json.loads(_extract_json(html))

    items: list[dict] = []
    _walk_items(data, items)

    dramas: list[Drama] = []
    seen: set[str] = set()
    for it in items:
        title = (it.get("title") or "").strip()
        if not title:
            continue

        mark = it.get("mark") or {}
        mark_text = (mark.get("text") or "").strip() if isinstance(mark, dict) else ""
        if mark_text in _NON_EPISODE_MARKS:
            continue

        vid = (it.get("action_value") or "").strip()
        # Only keep items that are real shows (have a resolvable id).
        if not vid or (it.get("action_type") or "") not in ("JUMP_TO_SHOW", ""):
            if not vid:
                continue

        badge = (it.get("lbTexts") or "").strip()
        tags = [t for t in (mark_text,) if t]

        if title in seen:
            continue
        seen.add(title)

        dramas.append(Drama(
            platform="优酷",
            title=title,
            episode_text=badge,
            subtitle=(it.get("subtitle") or "").strip(),
            tags=tags,
            url=f"https://v.youku.com/video?id={vid}" if vid else "",
            has_update=bool((it.get("updateTips") or "").strip()),
        ))
    return dramas


def iter_dramas() -> Iterator[Drama]:
    yield from collect()
