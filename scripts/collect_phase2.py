#!/usr/bin/env python3
"""SkillHandoffBench Phase 2：把一组官方 run 目录汇总成 Gate B / Gate C 的统计表。

输入：`<run-root>/robocombine/<track>/Motus/<run_id>/tasks/<task>/evaluation_statistics.json`
输出（写到 --out）：
  - `tasks.csv`     每个任务一行：stage1 / stage2 / ordered / transition conversion / 切换次数 / 首次失败阶段 / 步数
  - `episodes.csv`  每个 episode 一行：seed、成功、各阶段完成步、cue/switch 步、总步数
  - `summary.json`  带分子/分母 + Wilson 95%

用法：
  python3 scripts/collect_phase2.py --run-root results/phase2/gateB_full_inst --out results/phase2/gateB_full_inst/_summary
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import os
import sys


def wilson(k, n, z=1.959963984540054):
    if n <= 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def rate(k, n):
    return {"numerator": k, "denominator": n, "rate": (k / n if n else None), "wilson95": wilson(k, n)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", default=None)
    args = ap.parse_args()

    patterns = [
        # run_split 的 output-root 布局
        os.path.join(args.run_root, "robocombine", "*", "Motus", "*", "tasks", "*", "evaluation_statistics.json"),
        # 直接给到某个 run 目录（例如 results/<run>/official）
        os.path.join(args.run_root, "tasks", "*", "evaluation_statistics.json"),
    ]
    files = sorted({p for pat in patterns for p in glob.glob(pat)})
    if not files:
        print(f"no evaluation_statistics.json under {args.run_root} (tried {len(patterns)} layouts)")
        return 2

    os.makedirs(args.out, exist_ok=True)
    task_rows, ep_rows, per_task_metrics = [], [], {}

    for path in files:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        meta = d.get("metadata", {})
        task = meta.get("task_name") or os.path.basename(os.path.dirname(path))
        eps = d.get("episode_details") or []

        n_ep = len(eps)
        n_succ = sum(1 for e in eps if e.get("success"))
        n_s1 = sum(1 for e in eps if e.get("s1_completed"))
        n_s2 = sum(1 for e in eps if e.get("s2_completed"))
        switched = [e for e in eps if (e.get("switch_events") or [])]
        n_sw = len(switched)
        n_down = sum(1 for e in switched if e.get("s2_completed"))
        steps = [e.get("total_steps") for e in eps if e.get("total_steps") is not None]
        switch_steps = [e.get("switch_step") for e in switched if e.get("switch_step") is not None]
        cue_steps = []
        for e in switched:
            for ev in (e.get("switch_events") or []):
                if ev.get("cue_step") is not None:
                    cue_steps.append(ev["cue_step"])
        deltas = [s - c for s, c in zip(switch_steps, cue_steps)] if len(switch_steps) == len(cue_steps) else []

        # 首次失败位置（以"第一个未完成的阶段"为准）
        first_fail = []
        for e in eps:
            if e.get("success"):
                continue
            if not e.get("s1_completed"):
                first_fail.append("stage1")
            elif not e.get("s2_completed"):
                first_fail.append("stage2")
            else:
                first_fail.append("post_success_check")
        fail_counts = {}
        for f in first_fail:
            fail_counts[f] = fail_counts.get(f, 0) + 1

        per_task_metrics[task] = {
            "episodes": n_ep,
            "ordered_success": rate(n_succ, n_ep),
            "stage1_success": rate(n_s1, n_ep),
            "stage2_success": rate(n_s2, n_ep),
            # 任务书 Gate C 的定义：Transition conversion = 第二阶段成功 / 第一阶段成功
            "transition_conversion": rate(n_s2, n_s1),
            # 另一个更容易暴露"交接失败"的口径：已发生切换的 episode 里第二阶段成功的比例
            "downstream_success_among_switched": rate(n_down, n_sw),
            "switch_episodes": n_sw,
            "first_failure_position": fail_counts,
            "steps": {"mean": (sum(steps) / len(steps) if steps else None),
                      "min": min(steps) if steps else None, "max": max(steps) if steps else None},
            "cue_to_switch_steps": {"values": deltas, "mean": (sum(deltas) / len(deltas) if deltas else None)},
            "seeds": [e.get("seed") for e in eps],
            "stats_path": path,
        }

        task_rows.append({
            "task": task, "episodes": n_ep, "ordered_success": f"{n_succ}/{n_ep}",
            "stage1_success": f"{n_s1}/{n_ep}", "stage2_success": f"{n_s2}/{n_ep}",
            "transition_conversion": f"{n_down}/{n_sw}", "switch_episodes": n_sw,
            "first_failure": json.dumps(fail_counts, ensure_ascii=False),
            "steps_mean": round(sum(steps) / len(steps), 1) if steps else None,
            "steps_max": max(steps) if steps else None,
            "cue_to_switch_mean": round(sum(deltas) / len(deltas), 1) if deltas else None,
            "seeds": " ".join(str(e.get("seed")) for e in eps),
        })

        for e in eps:
            evs = e.get("switch_events") or []
            first = evs[0] if evs else {}
            ep_rows.append({
                "task": task, "seed": e.get("seed"), "success": e.get("success"),
                "s1_completed": e.get("s1_completed"), "s2_completed": e.get("s2_completed"),
                "total_steps": e.get("total_steps"),
                "s1_step": e.get("s1_step"), "s2_step": e.get("s2_step"),
                "switch_step": e.get("switch_step"), "cue_step": first.get("cue_step"),
                "cue_to_switch": (e.get("switch_step") - first.get("cue_step"))
                                 if (e.get("switch_step") is not None and first.get("cue_step") is not None) else None,
                "cache_cleared": first.get("cache_cleared"),
                "mechanism": first.get("source"),
                "n_switch_events": len(evs),
            })

    total_ep = sum(v["episodes"] for v in per_task_metrics.values())
    total_succ = sum(v["ordered_success"]["numerator"] for v in per_task_metrics.values())
    total_s1 = sum(v["stage1_success"]["numerator"] for v in per_task_metrics.values())
    total_s2 = sum(v["stage2_success"]["numerator"] for v in per_task_metrics.values())
    total_sw = sum(v["switch_episodes"] for v in per_task_metrics.values())
    total_down = sum(v["transition_conversion"]["numerator"] for v in per_task_metrics.values())

    summary = {
        "label": args.label or os.path.basename(args.run_root.rstrip(os.sep)),
        "run_root": args.run_root,
        "tasks": len(per_task_metrics),
        "overall": {
            "ordered_success": rate(total_succ, total_ep),
            "stage1_success": rate(total_s1, total_ep),
            "stage2_success": rate(total_s2, total_ep),
            "transition_conversion": rate(total_s2, total_s1),
            "downstream_success_among_switched": rate(total_down, total_sw),
            "switch_episodes": total_sw,
        },
        "per_task": per_task_metrics,
    }

    with open(os.path.join(args.out, "tasks.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(task_rows[0].keys()))
        w.writeheader(); w.writerows(task_rows)
    with open(os.path.join(args.out, "episodes.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(ep_rows[0].keys()))
        w.writeheader(); w.writerows(ep_rows)
    with open(os.path.join(args.out, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)

    print(f"{summary['label']}: tasks={summary['tasks']} episodes={total_ep} "
          f"ordered={total_succ}/{total_ep} stage1={total_s1}/{total_ep} "
          f"conv(s2/s1)={total_s2}/{total_s1} down(among switched)={total_down}/{total_sw}")
    for t, v in per_task_metrics.items():
        print(f"  {t}: ordered={v['ordered_success']['numerator']}/{v['episodes']} "
              f"s1={v['stage1_success']['numerator']}/{v['episodes']} "
              f"s2={v['stage2_success']['numerator']}/{v['episodes']} "
              f"conv(s2/s1)={v['transition_conversion']['numerator']}/{v['transition_conversion']['denominator']} "
              f"down(among switched)={v['downstream_success_among_switched']['numerator']}/{v['downstream_success_among_switched']['denominator']} "
              f"fail={v['first_failure_position']}")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
