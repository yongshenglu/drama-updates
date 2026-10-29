"""Collect drama update status from the four mainland China video platforms.

Usage:
    python main.py                      # collect all platforms, write output/latest.html
    python main.py --platform youku,tencent
    python main.py --out report.html    # write to a different path
    python main.py --json               # also dump raw JSON next to the HTML
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from collector import COLLECTORS, ORDER  # noqa: E402
from collector.browser import close_browser  # noqa: E402
from render import render  # noqa: E402

ROOT = Path(__file__).resolve().parent
DEFAULT_OUT = ROOT / "output" / "latest.html"


def collect_all(keys: list[str]):
    """Collect each platform independently; one failure never blocks the rest."""
    by_platform: dict[str, list] = {}
    errors: dict[str, str] = {}

    for key in keys:
        name, fn = COLLECTORS[key]
        print(f"[{name}] 采集中 ...", flush=True)
        try:
            rows = fn()
            by_platform[name] = rows
            airing = sum(1 for d in rows if d.is_airing)
            print(f"[{name}] 成功 {len(rows)} 部（连载中 {airing}）", flush=True)
        except Exception as exc:
            by_platform[name] = []
            errors[name] = str(exc)
            print(f"[{name}] 失败: {exc}", file=sys.stderr, flush=True)
            if "--verbose" in sys.argv:
                traceback.print_exc()
    return by_platform, errors


def main() -> int:
    ap = argparse.ArgumentParser(description="采集国内四大视频平台剧集更新情况")
    ap.add_argument("--platform", default=",".join(ORDER),
                    help=f"逗号分隔的平台: {','.join(ORDER)}")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="输出 HTML 路径")
    ap.add_argument("--json", action="store_true", help="同时输出 JSON 数据")
    ap.add_argument("--verbose", action="store_true", help="打印完整堆栈")
    args = ap.parse_args()

    keys = [k.strip() for k in args.platform.split(",") if k.strip()]
    unknown = [k for k in keys if k not in COLLECTORS]
    if unknown:
        print(f"未知平台: {', '.join(unknown)}", file=sys.stderr)
        print(f"可用: {', '.join(ORDER)}", file=sys.stderr)
        return 2

    try:
        by_platform, errors = collect_all(keys)
    finally:
        close_browser()

    total = sum(len(v) for v in by_platform.values())
    if total == 0 and errors:
        print("所有平台均采集失败，未生成看板", file=sys.stderr)
        return 1

    ts = datetime.now()
    html_text = render(by_platform, errors, ts)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_text, encoding="utf-8")

    if args.json:
        jpath = out.with_suffix(".json")
        jpath.write_text(json.dumps(
            {"generated_at": ts.isoformat(timespec="seconds"),
             "errors": errors,
             "platforms": {n: [d.to_dict() for d in rows]
                           for n, rows in by_platform.items()}},
            ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"JSON -> {jpath}")

    print("-" * 52)
    for name, rows in by_platform.items():
        print(f"  {name:<6} {len(rows):>3} 部")
    if errors:
        for name, msg in errors.items():
            print(f"  ! {name}: {msg}")
    print(f"  合计 {total} 部")
    print(f"HTML  -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
