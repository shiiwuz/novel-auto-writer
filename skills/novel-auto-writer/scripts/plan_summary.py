#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_plan(outputs_dir: Path, project_id: str) -> dict:
    p = outputs_dir / project_id / "project_plan.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _print(s: str = "") -> None:
    print(s)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument(
        "--outputs-dir",
        default="projects/novel-writer-cli/outputs",
        help="path to outputs dir (default: projects/novel-writer-cli/outputs)",
    )
    args = ap.parse_args()

    outputs_dir = Path(args.outputs_dir)
    obj = _load_plan(outputs_dir, args.project)

    topic = obj.get("topic") or {}
    bible = obj.get("story_bible") or {}
    world = (bible.get("world") or {})
    chars = obj.get("characters") or []
    outline = obj.get("outline") or []
    contrasts = obj.get("contrast_catalog") or []

    _print(f"project_id\t{args.project}")
    _print(f"title\t{topic.get('title','')}")
    _print(f"genre\t{topic.get('genre','')}")
    _print(f"tone\t{topic.get('tone','')}")
    _print()

    _print("core_premise")
    _print(str(bible.get("core_premise") or "").strip())
    _print()

    _print("world")
    _print(f"era\t{world.get('era','')}")
    locs = world.get("locations") or []
    if isinstance(locs, list) and locs:
        _print("locations\t" + " | ".join([str(x) for x in locs[:8]]))
    _print(f"tech_or_magic\t{world.get('tech_or_magic','')}")
    _print()

    _print("main_conflict")
    _print(str(bible.get("main_conflict") or "").strip())
    _print()

    _print("characters")
    for c in chars[:10]:
        name = c.get("name") or ""
        role = c.get("role") or ""
        drive = c.get("private_drive") or ""
        _print(f"- {name} / {role} / {drive}")
    _print()

    _print("outline")
    for ch in outline:
        idx = ch.get("chapter")
        title = ch.get("title") or ""
        logline = ch.get("logline") or ""
        _print(f"- ch{idx}: {title} :: {logline}")
    _print()

    _print("contrast_catalog (top 8)")
    for it in contrasts[:8]:
        cid = it.get("id") or ""
        modern = it.get("modern") or ""
        year2015 = it.get("year2015") or ""
        payoff = it.get("scene_payoff") or ""
        _print(f"- {cid}: {modern}  <->  {year2015}  | payoff: {payoff}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
