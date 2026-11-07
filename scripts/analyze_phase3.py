#!/usr/bin/env python3
"""SkillHandoffBench Phase 3A · Gate D/E：把 trace JSONL + 官方统计合成"交接状态"表。

输入：
  --trace   results/phase3/trace/<task>.jsonl（SHB_TRACE_JSONL 产出）
  --stats   results/phase3/gateD/<task>/evaluation_statistics.json（官方）
输出：
  <out>/<task>_episodes.csv   每 episode 一行（含交接状态摘要）
  <out>/<task>_events.csv     每次 cue/switch 的完整状态（与 analyze_trace.py 兼容）
  <out>/<task>_summary.json   汇总

只读，不改任何官方文件。
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os

ARM_JOINT_COUNT = 6


def _load(path):
    recs = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def _first(recs, pred):
    for r in recs:
        if pred(r):
            return r
    return None


def _arm_q(rec, side="left"):
    j = (rec.get("joints") or {}).get(side) or {}
    qpos = j.get("qpos") or []
    idx = j.get("arm_joint_indices") or list(range(min(ARM_JOINT_COUNT, len(qpos))))
    return [qpos[i] for i in idx if i < len(qpos)]


def _dist(p, q):
    if not p or not q:
        return None
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(p, q)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", required=True)
    ap.add_argument("--stats", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", default=None)
    ap.add_argument("--post-window", type=int, default=30, help="切换后观察窗口（步）")
    args = ap.parse_args()

    recs = _load(args.trace)
    label = args.label or os.path.basename(args.trace).split(".")[0]
    os.makedirs(args.out, exist_ok=True)

    # 按 episode_start 切段
    episodes, cur = [], None
    for r in recs:
        if r.get("event") == "episode_start":
            cur = {"start": r, "recs": [r]}
            episodes.append(cur)
        elif cur is not None:
            cur["recs"].append(r)

    stats = {}
    if args.stats and os.path.exists(args.stats):
        d = json.load(open(args.stats, encoding="utf-8"))
        for i, e in enumerate(d.get("episode_details") or []):
            stats[i] = e

    rows, ev_rows = [], []
    for idx, ep in enumerate(episodes):
        rs = ep["recs"]
        start = ep["start"]
        seed = start.get("seed")
        end = _first(list(reversed(rs)), lambda r: r.get("event") == "episode_end") or {}
        official = stats.get(idx, {})

        cues = [r for r in rs if r.get("event") == "cue"]
        switches = [r for r in rs if r.get("event") == "switch"]
        cue = cues[0] if cues else None
        sw = switches[0] if switches else None

        # 切换时刻之后的第一条 action
        first_b_action, first_b_contact = None, None
        obj_disp = {}
        if sw is not None and sw.get("step") is not None:
            s0 = sw["step"]
            post = [r for r in rs if r.get("step") is not None and r["step"] >= s0]
            fa = _first(post, lambda r: r.get("event") == "action")
            if fa is not None:
                first_b_action = {
                    "step": fa.get("step"),
                    "vec": fa.get("action"),
                    "norm": (round(math.sqrt(sum(x * x for x in (fa.get("action") or []))), 6)
                             if fa.get("action") else None),
                }
            fc = _first(post, lambda r: r.get("event") == "post_action" and (r.get("contacts") or 0) > 0)
            if fc is not None:
                first_b_contact = {"step": fc.get("step"), "contacts": fc.get("contacts")}
            # 目标物体在 [switch, switch+window] 内的位移
            w = [r for r in rs if r.get("step") is not None and s0 <= r["step"] <= s0 + args.post_window]
            if w:
                o0 = w[0].get("objects") or {}
                o1 = w[-1].get("objects") or {}
                for k in o0:
                    if k in o1:
                        d = _dist((o0[k] or {}).get("p"), (o1[k] or {}).get("p"))
                        if d is not None:
                            obj_disp[k] = round(d, 4)

        def pack(r):
            if r is None:
                return {}
            return {
                "step": r.get("step"),
                "instruction": r.get("instruction"),
                "stage_idx": r.get("stage_idx"),
                "cache_len": r.get("action_cache_len"),
                "gripper_L": (r.get("gripper") or {}).get("left"),
                "gripper_R": (r.get("gripper") or {}).get("right"),
                "ee_L_p": ((r.get("ee_pose") or {}).get("left") or {}).get("p"),
                "ee_L_q": ((r.get("ee_pose") or {}).get("left") or {}).get("q"),
                "ee_R_p": ((r.get("ee_pose") or {}).get("right") or {}).get("p"),
                "arm_q_L": _arm_q(r, "left"),
                "contacts": r.get("contacts"),
                "objects": r.get("objects"),
            }

        cue_p, sw_p = pack(cue), pack(sw)
        row = {
            "task": label,
            "episode_idx": idx,
            "seed": seed,
            "success_official": official.get("success", end.get("success")),
            "total_steps_official": official.get("total_steps", end.get("total_steps")),
            "s1_completed": official.get("s1_completed"),
            "s2_completed": official.get("s2_completed"),
            "s1_step": official.get("s1_step"),
            "s2_step": official.get("s2_step"),
            "cue_step": cue_p.get("step"),
            "switch_step": sw_p.get("step"),
            "cue_to_switch": ((sw_p.get("step") - cue_p.get("step"))
                              if cue_p.get("step") is not None and sw_p.get("step") is not None else None),
            "cue_instruction": cue_p.get("instruction"),
            "switch_instruction": sw_p.get("instruction"),
            "cue_cache_len": cue_p.get("cache_len"),
            "switch_cache_len": sw_p.get("cache_len"),
            "cue_gripper_L": cue_p.get("gripper_L"),
            "cue_gripper_R": cue_p.get("gripper_R"),
            "switch_gripper_L": sw_p.get("gripper_L"),
            "switch_gripper_R": sw_p.get("gripper_R"),
            "cue_contacts": cue_p.get("contacts"),
            "switch_contacts": sw_p.get("contacts"),
            "first_b_action_step": (first_b_action or {}).get("step"),
            "first_b_action_norm": (first_b_action or {}).get("norm"),
            "first_b_contact_step": (first_b_contact or {}).get("step"),
            "cue_ee_L_p": json.dumps(cue_p.get("ee_L_p")),
            "switch_ee_L_p": json.dumps(sw_p.get("ee_L_p")),
            "cue_ee_L_q": json.dumps(cue_p.get("ee_L_q")),
            "switch_ee_L_q": json.dumps(sw_p.get("ee_L_q")),
            "cue_arm_q_L": json.dumps(cue_p.get("arm_q_L")),
            "switch_arm_q_L": json.dumps(sw_p.get("arm_q_L")),
            "obj_disp_post_switch": json.dumps(obj_disp),
            "n_records": len(rs),
        }
        rows.append(row)

        for ev_name, ev in (("cue", cue), ("switch", sw)):
            if ev is None:
                continue
            p = pack(ev)
            ev_rows.append({"task": label, "episode_idx": idx, "seed": seed, "event": ev_name, **p,
                            "objects": json.dumps(p.get("objects"))})

    def _w(name, data):
        if not data:
            return None
        path = os.path.join(args.out, f"{label}_{name}.csv")
        with open(path, "w", newline="", encoding="utf-8") as fh:
            wr = csv.DictWriter(fh, fieldnames=list(data[0].keys()))
            wr.writeheader()
            wr.writerows(data)
        return path

    p1 = _w("episodes", rows)
    p2 = _w("events", ev_rows)

    n = len(rows)
    succ = sum(1 for r in rows if r["success_official"])
    s1 = sum(1 for r in rows if r["s1_completed"])
    s2 = sum(1 for r in rows if r["s2_completed"] and r["s1_completed"])
    deltas = [r["cue_to_switch"] for r in rows if r["cue_to_switch"] is not None]
    summary = {
        "label": label,
        "episodes": n,
        "environment_success": f"{succ}/{n}",
        "stage1_success": f"{s1}/{n}",
        "transition_conversion": f"{s2}/{s1}" if s1 else "0/0",
        "cue_to_switch_steps": {"values": deltas,
                                "mean": (sum(deltas) / len(deltas) if deltas else None)},
        "episodes_csv": p1,
        "events_csv": p2,
        "rows": rows,
    }
    with open(os.path.join(args.out, f"{label}_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)

    print(f"{label}: episodes={n} env_success={summary['environment_success']} "
          f"stage1={summary['stage1_success']} conv={summary['transition_conversion']} "
          f"cue_to_switch={deltas}")
    for r in rows:
        print(f"  ep{r['episode_idx']} seed={r['seed']} succ={r['success_official']} "
              f"steps={r['total_steps_official']} s1@={r['s1_step']} s2@={r['s2_step']} "
              f"cue={r['cue_step']} switch={r['switch_step']} Δ={r['cue_to_switch']} "
              f"B_action@{r['first_b_action_step']} B_contact@{r['first_b_contact_step']}")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
