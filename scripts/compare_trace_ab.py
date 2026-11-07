#!/usr/bin/env python3
"""SkillHandoffBench Phase 2 · Gate D：比较"启用/停用日志"的 A/B 三次运行。

判定标准（任一不满足 → docs/08 只能写 PARTIAL）：
  1. evaluation_statistics 的关键字段逐位相同：seed / success / total_steps / s1_step / s2_step / switch_step；
  2. 三份 task.log 归一化后逐行相同（去掉 `step_time=`、`[Timing]`、时间戳等非确定性内容）；
  3. actions_only 与 full 两次运行记录的 action 序列逐元素相同（容差 tol）；
  4. 静态检查：shb_trace.py 不含任何 RNG 调用（np.random / random / torch.rand*）。

用法：
    python3 scripts/compare_trace_ab.py --root results/phase2/trace --tol 1e-9
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

KEY_FIELDS = ["seed", "success", "total_steps", "s1_step", "s2_step", "switch_step"]


def find_stats(tag_dir):
    hits = glob.glob(os.path.join(tag_dir, "robocombine", "*", "Motus", "*", "tasks", "*", "evaluation_statistics.json"))
    return hits[0] if hits else None


def find_log(tag_dir):
    hits = glob.glob(os.path.join(tag_dir, "robocombine", "*", "Motus", "*", "tasks", "*", "task.log"))
    return hits[0] if hits else None


def normalize_log(path):
    """去掉非确定性内容，保留"行为可观测"的行。"""
    keep = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.replace("\r", "\n")
            for piece in line.split("\n"):
                p = piece.strip()
                if not p:
                    continue
                # 含 step_time/timing 的行去掉时间；保留结构与数值
                p = re.sub(r"step_time=[0-9.]+s", "step_time=NA", p)
                p = re.sub(r"\[Timing\][^\n]*", "[Timing] NA", p)
                p = re.sub(r"^\d{2}:\d{2}:\d{2}", "TS", p)
                if p.startswith("# command") or p.startswith("# cwd"):
                    continue
                keep.append(p)
    return keep


def stats_key_values(path):
    d = json.load(open(path, encoding="utf-8"))
    m = d["metadata"]
    out = {"total_episodes": m["total_episodes"], "total_successes": m["total_successes"],
           "overall_success_rate": m["overall_success_rate"]}
    eps = d.get("episode_details") or []
    if eps:
        e = eps[0]
        for k in KEY_FIELDS:
            out[k] = e.get(k)
    return d, out


def load_actions(path):
    acts = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get("event") == "action" and isinstance(r.get("action"), list):
            acts.append(r["action"])
    return acts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--tol", type=float, default=1e-9)
    ap.add_argument("--trace-src", default=os.path.join(os.path.dirname(__file__), "shb_trace.py"))
    args = ap.parse_args()

    tags = ["ab_off", "ab_actions_only", "ab_full"]
    result = {"checks": [], "ok": True}

    def check(name, ok, detail):
        result["checks"].append({"name": name, "ok": bool(ok), "detail": detail})
        if not ok:
            result["ok"] = False
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    # 1) stats
    stats = {}
    for tag in tags:
        p = find_stats(os.path.join(args.root, tag))
        if not p:
            check(f"stats[{tag}]", False, "evaluation_statistics.json not found")
            continue
        _, kv = stats_key_values(p)
        stats[tag] = kv
        print(f"  {tag}: {json.dumps(kv, ensure_ascii=False)}")
    if len(stats) == len(tags):
        ref = stats["ab_off"]
        for tag in tags[1:]:
            diff = {k: (ref.get(k), stats[tag].get(k)) for k in set(ref) | set(stats[tag])
                    if ref.get(k) != stats[tag].get(k)}
            check(f"stats_equal[off vs {tag}]", not diff, diff or "identical")

    # 2) task.log
    logs = {tag: find_log(os.path.join(args.root, tag)) for tag in tags}
    if all(logs.values()):
        norm = {tag: normalize_log(p) for tag, p in logs.items()}
        base = norm["ab_off"]
        for tag in tags[1:]:
            other = norm[tag]
            same = base == other
            if not same:
                i = next((i for i, (a, b) in enumerate(zip(base, other)) if a != b), min(len(base), len(other)))
                detail = f"differ at line {i}: {base[i:i+1]} vs {other[i:i+1]} (len {len(base)} vs {len(other)})"
            else:
                detail = f"identical ({len(base)} lines)"
            check(f"task_log_equal[off vs {tag}]", same, detail)
    else:
        check("task_log_found", False, {k: v for k, v in logs.items() if not v})

    # 3) actions
    a1 = os.path.join(args.root, "actions_only.jsonl")
    a2 = os.path.join(args.root, "full.jsonl")
    if os.path.exists(a1) and os.path.exists(a2):
        A, B = load_actions(a1), load_actions(a2)
        same_len = len(A) == len(B)
        maxdiff = 0.0
        if same_len:
            for x, y in zip(A, B):
                if len(x) != len(y):
                    maxdiff = float("inf")
                    break
                for a, b in zip(x, y):
                    maxdiff = max(maxdiff, abs(a - b))
        check("action_count_equal", same_len, f"{len(A)} vs {len(B)}")
        check(f"action_sequence_equal(tol={args.tol})", same_len and maxdiff <= args.tol,
              f"max_abs_diff={maxdiff}")
        result["n_actions"] = {"actions_only": len(A), "full": len(B), "max_abs_diff": maxdiff}
    else:
        check("action_traces_found", False, f"{a1} / {a2}")

    # 4) 静态 RNG 检查
    if os.path.exists(args.trace_src):
        src = open(args.trace_src, encoding="utf-8").read()
        bad = [pat for pat in ("np.random", "numpy.random", "random.random", "random.randint",
                               "torch.rand", "torch.randn", "torch.manual_seed") if pat in src]
        check("no_rng_in_trace", not bad, bad or "no RNG calls found")
    else:
        check("trace_src_found", False, args.trace_src)

    out = os.path.join(args.root, "ab_comparison.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
    print(f"\nverdict: {'PASS' if result['ok'] else 'PARTIAL'}  -> {out}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
