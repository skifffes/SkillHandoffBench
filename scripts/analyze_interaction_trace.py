#!/usr/bin/env python3
"""Phase 4D：分析 interaction 任务的 trace，判断"子任务完成事件"是瞬态还是持续。

输入：
  --trace   results/phase4d_trace/<task>.jsonl
  --stats   results/paper_table1/full/... 里同一任务的历史 evaluation_statistics.json（可选，用于复现性对照）
  --seeds   本次实际使用的 seed 列表文件（可选）
输出：
  每个 episode 的判定 + 关键时间序列（打印 + --out 的 JSON）

判定口径（任务书要求）：
  TRANSIENT_EVENT_CONFIRMED            开关在触发后回落到阈值以下（物理条件不再成立）
  PERSISTENT_EVENT_BUT_TERMINAL_FAILURE 开关持续满足阈值，但终局（夹爪）未达标
  OTHER_FAILURE                        其他已确认机制（如 S2 从未触发、S1 从未触发）
  INCONCLUSIVE                         证据不足

只读；不改任何官方行为。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

THRESH_OFFSET = 0.05   # 官方判据：qpos[0] >= limit[1] - 0.05


def load_jsonl(path):
    recs = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def split_episodes(recs):
    eps, cur = [], None
    for r in recs:
        if r.get("event") == "episode_start":
            cur = {"start": r, "recs": [r]}
            eps.append(cur)
        elif cur is not None:
            cur["recs"].append(r)
    return eps


def switch_series(recs, name="switch"):
    """返回 [(step, qpos0, trigger_ok)]，只取含该铰接对象的记录。"""
    out = []
    for r in recs:
        art = r.get("articulated") or {}
        item = art.get(name)
        if not item or not item.get("qpos"):
            continue
        q0 = item["qpos"][0]
        lim = item.get("qlimits") or [[None, None]]
        hi = lim[0][1]
        out.append((r.get("step"), q0, hi, bool(item.get("trigger_hi_minus_0.05"))))
    return out


def analyze_episode(ep, task):
    recs = ep["recs"]
    seed = ep["start"].get("seed")
    steps = [r.get("step") for r in recs if r.get("step") is not None]
    res = {"task": task, "seed": seed, "n_records": len(recs),
           "first_step": min(steps) if steps else None, "last_step": max(steps) if steps else None}

    # 首次触发时刻
    first = {}
    for i in range(2):
        for r in recs:
            fl = r.get("subtask_completed") or []
            if len(fl) > i and fl[i]:
                first[f"s{i+1}_step"] = r.get("step")
                first[f"s{i+1}_gripper"] = r.get("gripper")
                break
        first.setdefault(f"s{i+1}_step", None)
    res.update(first)

    # 终局
    end = recs[-1]
    res["end_flags"] = end.get("subtask_completed")
    res["end_gripper"] = end.get("gripper")
    res["eval_success_end"] = end.get("eval_success")
    succ_steps = [r.get("step") for r in recs if r.get("eval_success")]
    res["eval_success_first_step"] = succ_steps[0] if succ_steps else None

    # 开关关节持续性
    sw = switch_series(recs)
    if sw:
        s2_step = res.get("s2_step")
        after = [x for x in sw if s2_step is not None and x[0] is not None and x[0] >= s2_step]
        hi = after[0][2] if after else None
        thr = (hi - THRESH_OFFSET) if hi is not None else None
        res["switch_hi_limit"] = hi
        res["switch_threshold"] = thr
        res["switch_qpos_at_s2"] = after[0][1] if after else None
        below = [x for x in after if thr is not None and x[1] < thr]
        # 以"唯一步数"计，而不是记录条数（每步有 pre/post 两条）
        below_steps = sorted({x[0] for x in below if x[0] is not None})
        res["switch_steps_below_after_s2"] = len(below_steps)
        res["switch_records_below_after_s2"] = len(below)
        if below_steps and s2_step is not None:
            res["switch_rebound_first_step"] = below_steps[0]
            res["switch_rebound_last_step"] = below_steps[-1]
            res["switch_rebound_span_steps"] = below_steps[-1] - below_steps[0] + 1
        res["switch_min_after_s2"] = min((x[1] for x in after), default=None)
        res["switch_max_after_s2"] = max((x[1] for x in after), default=None)
        res["switch_rebound_margin"] = (round(thr - res["switch_min_after_s2"], 4)
                                        if (thr is not None and res["switch_min_after_s2"] is not None) else None)
        res["switch_rebound_duration_steps"] = len(below)
        res["switch_ever_below_after_s2"] = bool(below)
        # 开关首次"触发后仍高于阈值"的连续区间
        res["switch_last_qpos"] = sw[-1][1]

    # 夹爪在终局是否张开（用官方阈值 0.8 / 0.2 两个口径都记）
    g = res.get("end_gripper") or {}
    res["gripper_left_end"] = g.get("left")
    res["gripper_right_end"] = g.get("right")

    # 判定
    flags_end = res.get("end_flags") or []
    both_fired = len(flags_end) >= 2 and all(flags_end[:2])
    if res.get("eval_success_first_step") is not None:
        verdict = "SUCCESS_CONTROL"
    elif res.get("s2_step") is None:
        verdict = "OTHER_FAILURE"
        res["mechanism"] = "S2 从未触发"
    elif res.get("switch_ever_below_after_s2"):
        verdict = "TRANSIENT_EVENT_CONFIRMED"
        res["mechanism"] = "开关触发后回落到阈值以下"
    elif both_fired:
        verdict = "PERSISTENT_EVENT_BUT_TERMINAL_FAILURE"
        res["mechanism"] = "开关持续满足阈值、两标志为真，但终局夹爪未达标"
    else:
        verdict = "INCONCLUSIVE"
    res["verdict"] = verdict
    return res


def historical_outcome(stats_path, seed):
    """从历史 run 里取同 seed 的 s1/s2/success，用于 NON_REPRODUCED 判定。"""
    if not stats_path or not os.path.exists(stats_path):
        return None
    d = json.load(open(stats_path, encoding="utf-8"))
    for e in d.get("episode_details") or []:
        if e.get("seed") == seed:
            return {"s1_step": e.get("s1_step"), "s2_step": e.get("s2_step"),
                    "success": e.get("success"), "total_steps": e.get("total_steps")}
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", required=True)
    ap.add_argument("--task", default=None)
    ap.add_argument("--stats", default=None, help="历史 evaluation_statistics.json（可选）")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    task = args.task or os.path.basename(args.trace).replace(".jsonl", "")
    recs = load_jsonl(args.trace)
    eps = split_episodes(recs)
    results = [analyze_episode(ep, task) for ep in eps]

    for r in results:
        h = historical_outcome(args.stats, r["seed"])
        r["historical"] = h
        if h:
            same = (h["s1_step"] == r.get("s1_step") and h["s2_step"] == r.get("s2_step")
                    and bool(h["success"]) == (r.get("eval_success_first_step") is not None))
            r["historical_total_steps"] = h.get("total_steps")
            r["trace_last_step"] = r.get("last_step")
            r["steps_match"] = (h.get("total_steps") == r.get("last_step"))
            r["reproduced"] = bool(same)
            if not same:
                r["verdict"] = "NON_REPRODUCED"
            elif not r["steps_match"]:
                r["aborted_early"] = True   # s1/s2/success 一致但步数不同 → 中途 UnStableError 中止

    print(f"== {task}: {len(results)} episode(s)")
    for r in results:
        print(f"  seed={r['seed']} verdict={r['verdict']} "
              f"s1@{r.get('s1_step')} s2@{r.get('s2_step')} "
              f"switch[at s2]={r.get('switch_qpos_at_s2')} min={r.get('switch_min_after_s2')} "
              f"thr={r.get('switch_threshold')} below={r.get('switch_steps_below_after_s2')} "
              f"grip_end=L{r.get('gripper_left_end')}/R{r.get('gripper_right_end')} "
              f"succ@{r.get('eval_success_first_step')} reproduced={r.get('reproduced')}")
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        json.dump(results, open(args.out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
