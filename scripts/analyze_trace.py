#!/usr/bin/env python3
"""SkillHandoffBench Phase 2 · Gate D：把 JSONL 轨迹整理成"交接事件表"。

关键点（见 docs/05 §8）：**Oracle cue ≠ 实际切换**。
  A. cue            —— 完成信号第一次为真（`subtask_completed[stage]` 变 True）
  B. chunk 排空     —— 切换前最后一个被执行的 action（`--clear-cache false` 下的真实边界）
  C. 切换后第一次推理前 —— switch 事件之后的第一条 `pre_action`
  D. B 首条动作执行后 —— switch 之后的第一条 `action` 记录（take_action 被包装的那层）
  E. episode 结束    —— `episode_end`（成功/超时/失败）

本脚本不做任何推测：所有时间步都直接取自记录里的 `step`，并额外输出
`cue_to_switch_steps` 与 `cue_to_first_B_action_steps`，让"信号"和"执行"在数值上分开。

用法：
    python3 scripts/analyze_trace.py --trace results/phase2/trace/full.jsonl \
        --out results/phase2/trace/
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from collections import defaultdict


def load(path):
    recs = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", default="trace")
    args = ap.parse_args()

    recs = load(args.trace)
    episodes = defaultdict(list)
    for r in recs:
        episodes[r.get("episode_idx")].append(r)

    os.makedirs(args.out, exist_ok=True)
    rows = []
    summary = {"label": args.label, "episodes": [], "n_records": len(recs)}

    for ep_idx in sorted(episodes):
        rs = sorted(episodes[ep_idx], key=lambda r: r.get("seq", 0))
        start = next((r for r in rs if r["event"] == "episode_start"), None)
        end = next((r for r in reversed(rs) if r["event"] == "episode_end"), None)
        events = [r for r in rs if r["event"] in {"cue", "switch"}]

        # 以 switch 为界，找 B（switch 前最后一个 action）与 C/D（switch 后第一个 pre_action/action）
        for ev in events:
            if ev["event"] != "switch":
                continue
            seq = ev.get("seq", 0)
            before_actions = [r for r in rs if r["event"] == "action" and r.get("seq", 0) < seq]
            after_actions = [r for r in rs if r["event"] == "action" and r.get("seq", 0) > seq]
            after_pre = [r for r in rs if r["event"] == "pre_action" and r.get("seq", 0) > seq]
            cue = None
            for c in [r for r in rs if r["event"] == "cue"]:
                if c.get("stage_idx") == ev.get("from_subtask_idx") or cue is None:
                    cue = c
            row = {
                "episode_idx": ep_idx,
                "seed": (start or {}).get("seed"),
                "mechanism": ev.get("mechanism"),
                "from_stage": ev.get("from_subtask_idx"),
                "to_stage": ev.get("to_subtask_idx"),
                "cue_step": (cue or {}).get("step"),
                "switch_step": ev.get("step"),
                "cue_to_switch_steps": (
                    (ev.get("step") - (cue or {}).get("step"))
                    if (cue and ev.get("step") is not None and (cue or {}).get("step") is not None) else None
                ),
                "pre_switch_action_step": before_actions[-1].get("step") if before_actions else None,
                "post_switch_action_step": after_actions[0].get("step") if after_actions else None,
                "post_switch_pre_action_step": after_pre[0].get("step") if after_pre else None,
                "cue_instruction": (cue or {}).get("instruction"),
                "switch_instruction": ev.get("instruction"),
                "cue_gripper_left": ((cue or {}).get("gripper") or {}).get("left"),
                "cue_gripper_right": ((cue or {}).get("gripper") or {}).get("right"),
                "switch_gripper_left": (ev.get("gripper") or {}).get("left"),
                "switch_gripper_right": (ev.get("gripper") or {}).get("right"),
                "cue_action_cache_len": (cue or {}).get("action_cache_len"),
                "switch_action_cache_len": ev.get("action_cache_len"),
                "cue_pending_switch": (cue or {}).get("pending_switch"),
                "switch_pending_switch": ev.get("pending_switch"),
                "cue_render_sha1": ((cue or {}).get("render_rgb") or {}).get("sha1"),
                "switch_render_sha1": (ev.get("render_rgb") or {}).get("sha1"),
            }
            row["cue_ee_pose_left"] = json.dumps(((cue or {}).get("ee_pose") or {}).get("left"))
            row["switch_ee_pose_left"] = json.dumps((ev.get("ee_pose") or {}).get("left"))
            row["cue_objects"] = json.dumps((cue or {}).get("objects"), sort_keys=True)
            row["switch_objects"] = json.dumps(ev.get("objects"), sort_keys=True)
            rows.append(row)

        summary["episodes"].append({
            "episode_idx": ep_idx,
            "seed": (start or {}).get("seed"),
            "initial_instruction": (start or {}).get("initial_instruction"),
            "stages_prompted": (start or {}).get("subtask_instructions"),
            "success": (end or {}).get("success"),
            "total_steps": (end or {}).get("total_steps"),
            "cue_steps": (end or {}).get("subtask_completion_steps"),
            "n_switch_events": len((end or {}).get("switch_events") or []),
            "n_records": len(rs),
        })

    if rows:
        keys = list(rows[0].keys())
        with open(os.path.join(args.out, f"{args.label}_handoff_events.csv"), "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
    with open(os.path.join(args.out, f"{args.label}_episodes.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)

    print(f"records={len(recs)} episodes={len(episodes)} switch_events={len(rows)}")
    for r in rows:
        print(f"  ep{r['episode_idx']} seed={r['seed']} cue={r['cue_step']} switch={r['switch_step']} "
              f"delta={r['cue_to_switch_steps']} mech={r['mechanism']} "
              f"cache@cue={r['cue_action_cache_len']} cache@switch={r['switch_action_cache_len']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
