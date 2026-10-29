"""Data model for a single drama entry collected from a platform."""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Optional

# Badge shapes differ per platform, and "全" may appear before or after the
# count ("全47集" vs "47集全"), so completeness is matched explicitly.
_RE_UPDATE = re.compile(r"更新至\s*第?\s*(\d+)\s*[集期话]")
_RE_TOTAL_LEAD = re.compile(r"全\s*(\d+)\s*[集期话]")          # 全47集
_RE_TOTAL_TRAIL = re.compile(r"(\d+)\s*[集期话]\s*全")         # 47集全
_RE_RANGE = re.compile(r"限免\s*(\d+)\s*-\s*(\d+)\s*集")       # 限免11-12集
_RE_FREE_EP = re.compile(r"限免\s*第?\s*(\d+)\s*[集期话]")     # 限免第11集
_RE_EP_NUM = re.compile(r"第\s*(\d+)\s*[集期话]")              # 第11集
_RE_DAY = re.compile(r"每[周天一二三四五六日末]+")


@dataclass
class Drama:
    platform: str
    title: str
    episode_text: str = ""
    url: str = ""
    subtitle: str = ""
    kind: str = ""            # 剧集 / 综艺 / 电影 ...
    publish_time: str = ""    # "YYYY-MM-DD HH:MM:SS" when the platform exposes it
    schedule: str = ""        # free-text update schedule, e.g. "会员每日20点更新2集"
    tags: list[str] = field(default_factory=list)
    actors: list[str] = field(default_factory=list)  # leading cast, best-effort
    has_update: bool = False  # platform flags this item as recently updated

    # --- derived -------------------------------------------------------
    @property
    def total_episodes(self) -> Optional[int]:
        """Episode count when the show is finished, else None."""
        for rx in (_RE_TOTAL_LEAD, _RE_TOTAL_TRAIL):
            m = rx.search(self.episode_text)
            if m:
                return int(m.group(1))
        return None

    @property
    def is_complete(self) -> bool:
        return self.total_episodes is not None

    @property
    def episode_num(self) -> Optional[int]:
        """Highest episode currently available."""
        if self.total_episodes is not None:
            return self.total_episodes
        for rx in (_RE_UPDATE, _RE_RANGE, _RE_FREE_EP, _RE_EP_NUM):
            m = rx.search(self.episode_text)
            if m:
                # The upper bound of a range is the newest released episode.
                return int(m.group(2) if rx is _RE_RANGE else m.group(1))
        return None

    @property
    def is_airing(self) -> bool:
        """True while the show is still being released."""
        return bool(self.episode_text) and not self.is_complete

    @property
    def status(self) -> str:
        if self.is_airing:
            return "连载中"
        if self.is_complete:
            return "已完结"
        return "未知"

    @property
    def updated_today(self) -> bool:
        """Only trustable when the platform supplied an exact publish time."""
        from datetime import date
        if not self.publish_time:
            return False
        try:
            d = date.fromisoformat(self.publish_time[:10])
        except ValueError:
            return False
        return d == date.today()

    def dedup_key(self) -> str:
        return f"{self.platform}|{self.title.strip()}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d.update(
            episode_num=self.episode_num,
            total_episodes=self.total_episodes,
            is_complete=self.is_complete,
            is_airing=self.is_airing,
            status=self.status,
            updated_today=self.updated_today,
        )
        return d
