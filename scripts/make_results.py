#!/usr/bin/env python3
"""SkillHandoffBench: 把官方 RoboCombine 运行目录整理成可审查的结果包。

输入：`handoff_eval_runs/robocombine/<track>/<policy>/<run_id>/`（run_split.py 产出）
输出：`results/<run_id>/`
  - run_manifest.json      运行元数据（commit / checkpoint / clear-cache / seed / 墙钟）
  - summary.json           6 个指标，每个都带分子/分母 + Wilson 95% 区间
  - per_task.csv           逐任务一行
  - episodes.csv           逐 episode 一行（seed、成功、阶段完成步、切换步）
  - official/              官方原始产物（task.log、evaluation_statistics.json、summary.*）

只用标准库；不修改官方任何文件，只读取。
用法：
  python3 scripts/make_results.py --official-run <dir> --out results/<run_id> \
      [--wall-seconds 1234] [--command "..."] [--checkpoint-sha256 ...]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))


def wilson(k: int, n: int, z: float = 1.959963984540054) -> list[float] | None:
    """Wilson score interval（小样本比 naive normal 更可靠）。"""
    if n <= 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return [max(0.0, centre - half), min(1.0, centre + half)]


def rate(k: int, n: int) -> dict:
    return {"numerator": k, "denominator": n, "rate": (k / n if n else None), "wilson95": wilson(k, n)}


def load_stats(official_run: str) -> list[dict]:
    tasks_dir = os.path.join(official_run, "tasks")
    out = []
    if not os.path.isdir(tasks_dir):
        return out
    for name in sorted(os.listdir(tasks_dir)):
        p = os.path.join(tasks_dir, name, "evaluation_statistics.json")
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8") as fh:
                out.append({"task": name, "path": p, "stats": json.load(fh)})
    return out


def episode_rows(task: str, stats: dict) -> list[dict]:
    rows = []
    for ep in stats.get("episode_details", []) or []:
        switches = ep.get("switch_events") or []
        first_switch = switches[0] if switches else None
        switch_step = ep.get("switch_step")
        if switch_step is None and first_switch is not None:
            switch_step = first_switch.get("switch_step")
        total = ep.get("total_steps")
        rows.append({
            "task": task,
            "seed": ep.get("seed"),
            "success": bool(ep.get("success")),
            "s1_completed": bool(ep.get("s1_completed")),
            "s2_completed": bool(ep.get("s2_completed")),
            "total_steps": total,
            "s1_step": ep.get("s1_step"),
            "s2_step": ep.get("s2_step"),
            "switch_step": switch_step,
            "switch_count": len(switches),
            "cache_cleared": (first_switch or {}).get("cache_cleared"),
            "cue_step": (first_switch or {}).get("cue_step"),
            "steps_after_switch": (total - switch_step) if (total is not None and switch_step is not None) else None,
        })
    return rows


def git_commit(path: str) -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=path, capture_output=True, text=True, timeout=20)
        return out.stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--official-run", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--wall-seconds", type=float, default=None)
    ap.add_argument("--command", default=None)
    ap.add_argument("--checkpoint-sha256", default=None)
    ap.add_argument("--repo-root", default=None)
    args = ap.parse_args()

    official_run = os.path.abspath(args.official_run)
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)

    official_manifest_path = os.path.join(official_run, "run_manifest.json")
    official_manifest = {}
    if os.path.isfile(official_manifest_path):
        with open(official_manifest_path, "r", encoding="utf-8") as fh:
            official_manifest = json.load(fh)

    objects = load_stats(official_run)
    rows: list[dict] = []
    for obj in objects:
        rows.extend(episode_rows(obj["task"], obj["stats"]))

    # ---- 指标 ----
    n_ep = len(rows)
    n_succ = sum(1 for r in rows if r["success"])
    n_s1 = sum(1 for r in rows if r["s1_completed"])
    switched = [r for r in rows if (r["switch_count"] or 0) > 0]
    n_switched = len(switched)
    n_downstream = sum(1 for r in switched if r["s2_completed"])
    extra = [r["steps_after_switch"] for r in switched if r["steps_after_switch"] is not None]

    metrics = {
        "1_ordered_success_rate": rate(n_succ, n_ep),
        "2_stage1_success_rate": rate(n_s1, n_ep),
        "3_transition_conversion": rate(n_switched, n_s1),
        "4_handoff_physical_feasibility": {
            "numerator": None, "denominator": None, "rate": None, "wilson95": None,
            "note": "本轮未实现连接动作/规划器，B4-B7 才需要（见 docs/02 §9）",
        },
        "5_downstream_skill_success": rate(n_downstream, n_switched),
        "6_handoff_extra_steps": {
            "numerator": None, "denominator": len(extra), "rate": None, "wilson95": None,
            "mean_steps_after_switch": (sum(extra) / len(extra)) if extra else None,
            "min": min(extra) if extra else None,
            "max": max(extra) if extra else None,
        },
    }

    per_task = []
    for obj in objects:
        st = obj["stats"]
        t_rows = [r for r in rows if r["task"] == obj["task"]]
        meta = st.get("metadata", {})
        per_task.append({
            "task": obj["task"],
            "episodes": meta.get("total_episodes"),
            "successes": meta.get("total_successes"),
            "overall_success_rate": meta.get("overall_success_rate"),
            "stage1_count": (st.get("subtask_completion", {}).get("any_order", {}).get("subtask_1", {}) or {}).get("count"),
            "stage2_count": (st.get("subtask_completion", {}).get("any_order", {}).get("subtask_2", {}) or {}).get("count"),
            "all_subtasks_count": (st.get("subtask_completion", {}).get("any_order", {}).get("all_subtasks", {}) or {}).get("count"),
            "episodes_with_switch": sum(1 for r in t_rows if (r["switch_count"] or 0) > 0),
            "timeout": (st.get("failure_analysis", {}).get("by_type", {}).get("timeout", {}) or {}).get("count"),
            "gripper_not_open": (st.get("failure_analysis", {}).get("by_type", {}).get("gripper_not_open", {}) or {}).get("count"),
            "subtask_incomplete": (st.get("failure_analysis", {}).get("by_type", {}).get("subtask_incomplete", {}) or {}).get("count"),
            "avg_episode_time_s": (st.get("timing", {}) or {}).get("avg_episode_time"),
            "avg_steps": (st.get("episode_steps", {}) or {}).get("avg"),
            "max_steps": (st.get("episode_steps", {}) or {}).get("max"),
            "stats_path": obj["path"],
        })

    manifest = {
        "run_id": os.path.basename(out),
        "generated_at": datetime.now(CST).isoformat(timespec="seconds"),
        "official_run_dir": official_run,
        "spec": official_manifest.get("spec"),
        "track": official_manifest.get("track"),
        "policy": official_manifest.get("policy"),
        "checkpoint": official_manifest.get("checkpoint"),
        "checkpoint_label": official_manifest.get("checkpoint_label"),
        "checkpoint_sha256": args.checkpoint_sha256,
        "max_steps_per_episode": official_manifest.get("max_steps_per_episode"),
        "task_count": official_manifest.get("task_count"),
        "robocombine_commit": git_commit(args.repo_root) if args.repo_root else None,
        "episodes_observed": n_ep,
        "wall_seconds": args.wall_seconds,
        "command": args.command,
        "seeds": sorted({r["seed"] for r in rows if r["seed"] is not None}),
        "python": sys.version.split()[0],
        "notes": [
            "clear_cache 由官方 run_manifest / 每条 episode 的 switch_events 记录",
            "指标口径见 docs/02 §4；每个 ratio 都带分子/分母",
        ],
    }

    summary = {
        "run_id": manifest["run_id"],
        "track": manifest["track"],
        "policy": manifest["policy"],
        "task_count": len(per_task),
        "episodes": n_ep,
        "metrics": metrics,
        "per_task": per_task,
        "official_summary": None,
    }
    official_summary_path = os.path.join(official_run, "summary.json")
    if os.path.isfile(official_summary_path):
        try:
            with open(official_summary_path, "r", encoding="utf-8") as fh:
                summary["official_summary"] = json.load(fh)
        except Exception:  # noqa: BLE001
            pass

    with open(os.path.join(out, "run_manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
    with open(os.path.join(out, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)

    if per_task:
        keys = list(per_task[0].keys())
        with open(os.path.join(out, "per_task.csv"), "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=keys)
            w.writeheader()
            w.writerows(per_task)
    if rows:
        keys = list(rows[0].keys())
        with open(os.path.join(out, "episodes.csv"), "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)

    # 官方原始产物原样复制（只读来源）；若目标就是源目录本身则跳过
    dst_official = os.path.join(out, "official")
    if os.path.realpath(dst_official) != os.path.realpath(official_run):
        if os.path.isdir(dst_official):
            shutil.rmtree(dst_official)
        shutil.copytree(official_run, dst_official)

    print(f"wrote {out}: episodes={n_ep} success={n_succ} s1={n_s1} switched={n_switched}")
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
