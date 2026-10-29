"""Render collected dramas into a self-contained, mobile-first HTML board."""
from __future__ import annotations

import html
import json
from datetime import datetime
from typing import Iterable, Optional

from collector.models import Drama

PLATFORM_ORDER = ["爱奇艺", "优酷", "腾讯视频", "芒果TV"]

PLATFORM_COLORS = {
    "爱奇艺": "#00be06",
    "优酷": "#00a0e9",
    "腾讯视频": "#ff650f",
    "芒果TV": "#ff8a00",
}


def _esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def _status_class(d: Drama) -> str:
    if d.is_airing:
        return "pill-airing"
    if d.is_complete:
        return "pill-done"
    return "pill-unknown"


def _sort_key(d: Drama):
    """Airing first, then most episodes, then alphabetically."""
    return (
        0 if d.is_airing else 1 if d.is_complete else 2,
        0 if d.updated_today else 1 if d.has_update else 2,
        -(d.episode_num or 0),
        d.title,
    )


def _card(d: Drama, color: str) -> str:
    ep = _esc(d.episode_text) or "—"
    sub = _esc(d.subtitle)
    sched = _esc(d.schedule)
    kind = _esc(d.kind)
    pub = _esc(d.publish_time)

    today_badge = '<span class="today">今日更新</span>' if d.updated_today else ""

    sub_html = f'<p class="sub">{sub}</p>' if sub else ""
    meta = []
    if d.actors:
        meta.append(f'<span class="meta-item cast">主演 {", ".join(_esc(a) for a in d.actors)}</span>')
    if sched:
        meta.append(f'<span class="meta-item">🗓 {sched}</span>')
    if pub:
        meta.append(f'<span class="meta-item">🕐 {pub}</span>')
    if kind:
        meta.append(f'<span class="meta-item">{kind}</span>')
    meta_html = f'<div class="meta">{"".join(meta)}</div>' if meta else ""

    return f"""
    <article class="card" data-status="{d.status}" data-platform="{_esc(d.platform)}">
      <div class="card-top">
        <h3 class="title">{_esc(d.title)}</h3>
        {today_badge}
      </div>
      <div class="badges">
        <span class="ep" style="--c:{color}">{ep}</span>
        <span class="pill {_status_class(d)}">{d.status}</span>
      </div>
      {sub_html}
      {meta_html}
    </article>"""


def _platform_section(name: str, dramas: Iterable[Drama], color: str,
                      error: Optional[str]) -> str:
    rows = sorted(dramas, key=_sort_key)
    if error and not rows:
        body = f'<p class="empty">采集失败：{_esc(error)}</p>'
    elif not rows:
        body = '<p class="empty">暂无数据</p>'
    else:
        body = "".join(_card(d, color) for d in rows)

    n_total = len(rows)
    n_airing = sum(1 for d in rows if d.is_airing)
    n_done = sum(1 for d in rows if d.is_complete)
    stats = f"{n_total} 部 · 连载中 {n_airing} · 完结 {n_done}"

    err_note = (f'<p class="errnote">部分数据采集失败：{_esc(error)}</p>'
                if error and rows else "")

    # Sections with no airing titles stay open in the default "all" view.
    open_attr = " open"

    return f"""
    <section class="platform" data-platform="{_esc(name)}">
      <details class="pbox"{open_attr}>
        <summary class="phead" style="--c:{color}">
          <h2>{_esc(name)}</h2>
          <span class="pstats">{stats}</span>
          <span class="chev" aria-hidden="true"></span>
        </summary>
        {err_note}
        <div class="grid">{body}</div>
        <p class="hidden-note" hidden>当前筛选下该平台没有匹配的剧集</p>
      </details>
    </section>"""


def render(by_platform: dict[str, list[Drama]],
           errors: dict[str, str],
           generated_at: Optional[datetime] = None) -> str:
    ts = generated_at or datetime.now()
    total = sum(len(v) for v in by_platform.values())
    airing = sum(1 for v in by_platform.values() for d in v if d.is_airing)

    tabs = ['<button class="tab active" data-filter="all">全部</button>']
    for name in PLATFORM_ORDER:
        if name not in by_platform:
            continue
        n = len(by_platform[name])
        tabs.append(
            f'<button class="tab" data-filter="{_esc(name)}">'
            f'{_esc(name)} <em>{n}</em></button>')

    n_airing = sum(1 for v in by_platform.values() for d in v if d.is_airing)
    n_done = sum(1 for v in by_platform.values() for d in v if d.is_complete)
    status_tabs = (
        '<button class="tab stab active" data-status="all">全部状态</button>'
        f'<button class="tab stab" data-status="连载中">连载中 <em>{n_airing}</em></button>'
        f'<button class="tab stab" data-status="已完结">已完结 <em>{n_done}</em></button>'
    )

    sections = "".join(
        _platform_section(name, by_platform.get(name, []),
                          PLATFORM_COLORS.get(name, "#888"), errors.get(name))
        for name in PLATFORM_ORDER if name in by_platform
    )

    payload = json.dumps(
        {name: [d.to_dict() for d in rows] for name, rows in by_platform.items()},
        ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0d1117">
<meta name="description" content="爱奇艺、优酷、腾讯视频、芒果TV 剧集更新情况汇总">
<title>剧集更新表</title>
<style>
:root {{
  --bg:#0d1117; --bg2:#161b22; --bg3:#1c2230; --line:#2a3140;
  --fg:#e6edf3; --fg2:#9aa4b2; --fg3:#6b7684; --acc:#58a6ff;
  --radius:14px;
}}
* {{ box-sizing:border-box; }}
html {{ -webkit-text-size-adjust:100%; }}
body {{
  margin:0; background:var(--bg); color:var(--fg);
  font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",
    "Helvetica Neue",Helvetica,Arial,sans-serif;
  line-height:1.5; -webkit-font-smoothing:antialiased;
}}
a {{ color:inherit; text-decoration:none; }}

/* ---------- header ---------- */
.hero {{
  position:sticky; top:0; z-index:20;
  background:linear-gradient(180deg,rgba(13,17,23,.98),rgba(13,17,23,.92));
  backdrop-filter:blur(10px);
  border-bottom:1px solid var(--line);
  padding:14px 16px 10px;
  padding-top:max(14px,env(safe-area-inset-top));
}}
.hero h1 {{ margin:0; font-size:20px; letter-spacing:.5px; }}
.hero .sub-line {{ margin:4px 0 0; font-size:12.5px; color:var(--fg2); }}
.hero .sub-line b {{ color:var(--fg); font-weight:600; }}
.tabs {{
  display:flex; gap:8px; overflow-x:auto; padding:12px 0 2px;
  scrollbar-width:none; -ms-overflow-style:none;
}}
.tabs::-webkit-scrollbar {{ display:none; }}
.tab {{
  flex:0 0 auto; border:1px solid var(--line); background:var(--bg2);
  color:var(--fg2); padding:7px 13px; border-radius:999px;
  font-size:13px; cursor:pointer; white-space:nowrap;
  font-family:inherit; transition:.15s;
}}
.tab em {{ font-style:normal; color:var(--fg3); margin-left:3px; font-size:12px; }}
.tab.active {{ background:var(--acc); border-color:var(--acc); color:#04121f; font-weight:600; }}
.tab.active em {{ color:#04121f; opacity:.7; }}
.status-tabs {{ padding-top:9px; }}
.status-tabs .tab {{ background:transparent; }}
.status-tabs .tab.active {{ background:var(--acc); }}

/* ---------- layout ---------- */
main {{ padding:16px 14px 40px; max-width:1180px; margin:0 auto; }}
.platform {{ margin-bottom:14px; }}
.platform[hidden] {{ display:none; }}
.pbox {{ border:1px solid var(--line); border-radius:var(--radius); background:var(--bg2); }}
.phead {{
  display:flex; align-items:center; gap:10px; flex-wrap:wrap;
  border-left:3px solid var(--c); padding:13px 14px; cursor:pointer;
  list-style:none; user-select:none;
}}
.phead::-webkit-details-marker {{ display:none; }}
.phead h2 {{ margin:0; font-size:17px; }}
.pstats {{ font-size:12px; color:var(--fg3); }}
.chev {{
  margin-left:auto; width:9px; height:9px; flex:0 0 auto;
  border-right:2px solid var(--fg3); border-bottom:2px solid var(--fg3);
  transform:rotate(45deg); transition:transform .18s;
}}
details:not([open]) > .phead .chev {{ transform:rotate(-45deg); }}
details:not([open]) .phead h2, details:not([open]) .pstats {{ opacity:.75; }}
.errnote {{
  font-size:12.5px; color:#f0b429; background:rgba(240,180,41,.09);
  border:1px solid rgba(240,180,41,.25); border-radius:10px;
  padding:8px 11px; margin:0 14px 12px;
}}
.empty {{ color:var(--fg3); font-size:13.5px; padding:14px 2px; }}
.hidden-note {{
  color:var(--fg3); font-size:13px; padding:0 16px 16px; margin:0;
}}
.hidden-note[hidden] {{ display:none; }}

.grid {{ display:grid; gap:11px; grid-template-columns:1fr; padding:0 12px 14px; }}
.card {{
  background:var(--bg2); border:1px solid var(--line); border-radius:var(--radius);
  padding:13px 14px; position:relative;
}}
.card-top {{ display:flex; align-items:flex-start; gap:8px; justify-content:space-between; }}
.title {{ margin:0; font-size:15.5px; font-weight:600; line-height:1.35; }}
.today {{
  flex:0 0 auto; font-size:11px; font-weight:600; color:#04121f;
  background:#3fb950; border-radius:6px; padding:2px 7px; white-space:nowrap;
}}
.badges {{ display:flex; gap:7px; flex-wrap:wrap; margin-top:9px; align-items:center; }}
.ep {{
  font-size:12.5px; font-weight:600; color:var(--c);
  background:color-mix(in srgb,var(--c) 15%,transparent);
  border:1px solid color-mix(in srgb,var(--c) 38%,transparent);
  border-radius:7px; padding:2px 8px;
}}
.pill {{ font-size:11.5px; border-radius:7px; padding:2px 8px; }}
.pill-airing {{ color:#3fb950; background:rgba(63,185,80,.13); }}
.pill-done {{ color:var(--fg3); background:rgba(139,148,158,.13); }}
.pill-unknown {{ color:#f0b429; background:rgba(240,180,41,.13); }}
.sub {{ margin:9px 0 0; font-size:13px; color:var(--fg2); }}
.meta {{ display:flex; gap:10px; flex-wrap:wrap; margin-top:8px; }}
.meta-item {{ font-size:12px; color:var(--fg3); }}
.meta-item.cast {{ color:var(--fg2); }}

footer {{
  border-top:1px solid var(--line); margin-top:14px; padding:18px 16px 30px;
  text-align:center; font-size:12px; color:var(--fg3);
}}
footer p {{ margin:3px 0; }}

/* ---------- wider screens ---------- */
@media (min-width:640px) {{
  .grid {{ grid-template-columns:repeat(2,1fr); }}
  .hero h1 {{ font-size:23px; }}
  main {{ padding:20px 22px 50px; }}
}}
@media (min-width:980px) {{
  .grid {{ grid-template-columns:repeat(3,1fr); }}
}}
@media (min-width:1320px) {{
  .grid {{ grid-template-columns:repeat(4,1fr); }}
}}
</style>
</head>
<body>
<header class="hero">
  <h1>剧集更新表</h1>
  <p class="sub-line">
    共 <b>{total}</b> 部 · 连载中 <b>{airing}</b> ·
    更新于 {ts.strftime("%Y-%m-%d %H:%M")}
  </p>
  <nav class="tabs">{"".join(tabs)}</nav>
  <nav class="tabs status-tabs">{status_tabs}</nav>
</header>

<main>{sections}</main>

<footer>
  <p>数据来自各平台公开页面，仅供个人追剧参考</p>
  <p>仅腾讯视频提供精确到集的更新时间，其余平台展示平台标记的更新状态</p>
  <p>优酷的公开页面不提供演职员信息，因此该平台不显示主演</p>
  <p>生成时间 {ts.strftime("%Y-%m-%d %H:%M:%S")}</p>
</footer>

<script>
(() => {{
  const platformTabs = document.querySelectorAll('.tab:not(.stab)');
  const statusTabs = document.querySelectorAll('.stab');
  const sections = document.querySelectorAll('.platform');
  let platform = 'all';
  let status = 'all';

  function apply() {{
    sections.forEach(section => {{
      const showSection = platform === 'all' || section.dataset.platform === platform;
      section.hidden = !showSection;
      if (!showSection) return;

      let visible = 0;
      section.querySelectorAll('.card').forEach(card => {{
        const match = status === 'all' || card.dataset.status === status;
        card.hidden = !match;
        if (match) visible++;
      }});
      const note = section.querySelector('.hidden-note');
      const grid = section.querySelector('.grid');
      if (note && grid) {{
        note.hidden = visible > 0;
        grid.hidden = visible === 0;
      }}
    }});
  }}

  platformTabs.forEach(btn => btn.addEventListener('click', () => {{
    platformTabs.forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    platform = btn.dataset.filter;
    apply();
  }}));

  statusTabs.forEach(btn => btn.addEventListener('click', () => {{
    statusTabs.forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    status = btn.dataset.status;
    apply();
  }}));
}})();
</script>
<script type="application/json" id="drama-data">{payload}</script>
</body>
</html>"""
