#!/usr/bin/env python3
"""离线计数审计：逐 (track, task) 核对 episode 数、重复 seed、中断 episode。

目的：回答"为什么总数是 669 而不是 735"这类计数矛盾。
只读 evaluation_statistics.json 的 episode_details，不重跑任何东西。

用法：
  python3 scripts/audit_episode_count.py --root results/paper_table1 --out results/paper_table1/count_audit.json
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from collections import defaultdict

TRACKS = ("oracle_hse", "full_inst")
SKIP = ("/gateD/", "/probe/", "/phase4d_trace/")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="results/paper_table1")
    ap.add_argument("--out", default=None)
    ap.add_argument("--max-steps", type=int, default=1500)
    args = ap.parse_args()

    runs = defaultdict(list)     # (track, task) -> [(n, seeds, aborted, path)]
    for p in glob.glob(os.path.join(args.root, "**", "tasks", "*", "evaluation_statistics.json"), recursive=True):
        if any(s in p for s in SKIP):
            continue
        parts = p.split(os.sep)
        track = next((x for x in parts if x in TRACKS), None)
        if not track:
            continue
        task = parts[-2]
        try:
            d = json.load(open(p, encoding="utf-8"))
            eps = d.get("episode_details") or []
        except Exception:
            continue
        if not eps:
            continue
        seeds = [e.get("seed") for e in eps]
        aborted = sum(1 for e in eps
                      if not e.get("success") and int(e.get("total_steps") or 0) < args.max_steps)
        runs[(track, task)].append((len(eps), seeds, aborted, p))

    pairs = sorted(runs)
    total = 0
    print("| Track | Task | canonical n | unique seeds | dup seeds | aborted | 其他 run |")
    print("| --- | --- | ---: | ---: | ---: | ---: | --- |")
    detail = {}
    for (track, task) in pairs:
        # 先按"唯一种子数"排序，再按记录数：避免 resume 造成的重复记录骗取 canonical
        cand = sorted(runs[(track, task)], key=lambda x: (-len(set(x[1])), -x[0]))
        n, seeds, aborted, path = cand[0]
        uniq = len(set(seeds))
        dup = len(seeds) - uniq
        others = len(cand) - 1
        total += n
        print(f"| {track.split('_')[0]} | {task.replace('_2tasks','')} | {n} | {uniq} | {dup} | {aborted} | {others} |")
        detail[f"{track}/{task}"] = {
            "n": n, "unique_seeds": uniq, "duplicate_seeds": dup, "aborted": aborted,
            "other_runs": others, "path": path,
            "sum_all_runs": sum(x[0] for x in cand),
        }

    print()
    print(f"pair 数: {len(pairs)}（应为 19 任务 × 2 轨道 = 38）")
    print(f"canonical episode 合计: {total}（满额 {len(pairs)*20}；若 38 对全满 = 760）")
    short = [(k, v["n"]) for k, v in detail.items() if v["n"] < 20]
    if short:
        print("未满 20 的 pair:")
        for k, n in short:
            print(f"  {k}: {n}/20")
    else:
        print("未满 20 的 pair: 无")

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        json.dump({"total": total, "pairs": detail,
                   "short": dict(short)},
                  open(args.out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
