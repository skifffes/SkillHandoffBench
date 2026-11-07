#!/usr/bin/env python3
"""SkillHandoffBench Phase 2：从官方 `task.log` 做**逐 episode 取证**（只读，不重跑）。

判断失败更像哪一种：
  (a) 下游原子能力不足 —— 第二阶段从未达成、状态长期不变
  (b) 交接状态不合适 —— 切换后长时间停滞/抖动，但第一阶段曾成功
  (c) 指令/chunk 延迟 —— 切换后旧指令仍执行很久

数据来源：环境 `check_success()` 打的
    [Step N] S1:✓ S2:✗ L:0.984(✓) R:1.000(✓) -> FAIL: S2
以及 `[Step N] Instruction='...'`。

切分：**按 step 编号回退**切 episode（每 episode 从 0 开始），
只含 1–2 条 step 记录的段判为"专家 demo 段"丢弃。指令记录按**行序号**归属到所属段。

注意（docs/05 §8）：日志按 `take_action_cnt` 去重打印，`take_action()` 内部会多次 `scene.step()`，
同一步内可能已经成功；**终局以 evaluation_statistics.json 为准**，本脚本只看行为形态。

用法：
    python3 scripts/forensics_episode.py --log <task.log> [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

STEP_PAT = re.compile(r"^\[Step\s+(\d+)\]\s*S1:(.)\s*S2:(.)\s*L:([0-9.]+)\(([^)]*)\)\s*R:([0-9.]+)\(([^)]*)\)")
INST_PAT = re.compile(r"^\[Step\s+(\d+)\]\s*Instruction='([^']*)'")


def parse(path):
    """单次扫描：返回 (records, instructions)，每条都带全局行序号 idx。"""
    recs, insts, idx = [], [], 0
    for raw in open(path, encoding="utf-8", errors="replace"):
        for piece in raw.replace("\r", "\n").split("\n"):
            s = piece.strip()
            if not s:
                continue
            idx += 1
            m = STEP_PAT.match(s)
            if m:
                # 专家 demo 的 SUCCESS 行是 `L:1.000() R:1.000()`（括号里为空），
                # 策略执行时括号里一定有 ✓/✗ —— 用它区分，避免把专家成绩混进 episode 统计。
                is_expert_line = not (m.group(5).strip() or m.group(7).strip())
                if is_expert_line:
                    continue
                recs.append({"idx": idx, "step": int(m.group(1)), "s1": m.group(2) == "✓",
                             "s2": m.group(3) == "✓", "lgrip": float(m.group(4)), "rgrip": float(m.group(6))})
                continue
            mi = INST_PAT.match(s)
            if mi:
                insts.append({"idx": idx, "step": int(mi.group(1)), "instruction": mi.group(2)})
    return recs, insts


def split_runs(recs):
    """按 step 回退切段，返回 [(start_idx, end_idx, [records])]。"""
    runs, cur, prev = [], [], None
    for r in recs:
        if prev is not None and r["step"] < prev:
            if cur:
                runs.append(cur)
            cur = []
        cur.append(r)
        prev = r["step"]
    if cur:
        runs.append(cur)
    return runs


def dedupe_instructions(items):
    out, last = [], None
    for i in items:
        if i["instruction"] != last:
            out.append({"step": i["step"], "instruction": i["instruction"]})
            last = i["instruction"]
    return out


def summarize(run, insts):
    # 专家 demo 的终局行是 `[Step 0] S1:✓ S2:✓ ...`（双阶段都完成）；
    # 策略 episode 在 step 0 时还没有执行任何动作，两个标志都是 False。
    # 用这个区分把专家行剔掉，避免把"专家成绩"混进 episode 统计。
    run = [r for r in run if not (r["step"] == 0 and r["s1"] and r["s2"])]
    if not run:
        return {"n_logged_steps": 0, "step_range": [None, None], "s1_ever": False, "s2_ever": False,
                "first_s1_step": None, "first_s2_step": None, "n_s2_true_logged": 0,
                "last_s2_true_step": None, "lgrip": None, "rgrip": None,
                "instruction_changes": [], "longest_plateaus": [], "stall_after_switch_hint": False}
    st = [s["step"] for s in run]
    lo, hi = min(st), max(st)
    lo_idx, hi_idx = run[0]["idx"], run[-1]["idx"]
    my_insts = [i for i in insts if lo_idx <= i["idx"] <= hi_idx]
    s1_steps = [s["step"] for s in run if s["s1"]]
    s2_steps = [s["step"] for s in run if s["s2"]]
    lg = [s["lgrip"] for s in run]
    rg = [s["rgrip"] for s in run]

    runs, cur_key, n = [], None, 0
    for s in run:
        key = (s["s1"], s["s2"])
        if key == cur_key:
            n += 1
        else:
            if cur_key is not None:
                runs.append({"pattern": list(cur_key), "len": n, "until_step": s["step"]})
            cur_key, n = key, 1
    runs.append({"pattern": list(cur_key), "len": n, "until_step": st[-1]})
    runs.sort(key=lambda r: -r["len"])

    return {
        "n_logged_steps": len(run),
        "step_range": [lo, hi],
        "s1_ever": bool(s1_steps), "s2_ever": bool(s2_steps),
        "first_s1_step": s1_steps[0] if s1_steps else None,
        "first_s2_step": s2_steps[0] if s2_steps else None,
        "n_s2_true_logged": len(s2_steps),
        "last_s2_true_step": s2_steps[-1] if s2_steps else None,
        "lgrip": {"min": min(lg), "max": max(lg), "mean": round(sum(lg) / len(lg), 3)} if lg else None,
        "rgrip": {"min": min(rg), "max": max(rg), "mean": round(sum(rg) / len(rg), 3)} if rg else None,
        "instruction_changes": dedupe_instructions(my_insts),
        "longest_plateaus": runs[:3],
        "stall_after_switch_hint": (
            runs[0]["pattern"] == [True, False] and runs[0]["len"] > 100
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    ap.add_argument("--json", default=None)
    ap.add_argument("--min-records", type=int, default=5)
    args = ap.parse_args()

    recs, insts = parse(args.log)
    runs = split_runs(recs)
    policy = [r for r in runs if len(r) >= args.min_records]
    report = {"log": args.log, "total_step_lines": len(recs), "runs": len(runs),
              "policy_episodes": len(policy), "items": []}

    for idx, run in enumerate(policy):
        item = {"episode_index": idx, **summarize(run, insts)}
        report["items"].append(item)
        ic = item["instruction_changes"]
        print(f"--- episode {idx}: steps {item['step_range']} (n={item['n_logged_steps']}) ---")
        print(f"    S1@{item['first_s1_step']}  S2@{item['first_s2_step']} "
              f"(S2 true in {item['n_s2_true_logged']} logged steps, last@{item['last_s2_true_step']})")
        print(f"    gripper L={item['lgrip']} R={item['rgrip']}")
        print(f"    instruction: " + " -> ".join(f"'{c['instruction']}'@{c['step']}" for c in ic))
        print(f"    plateaus={item['longest_plateaus']}  stall_hint={item['stall_after_switch_hint']}")

    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, ensure_ascii=False)
        print(f"-> {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
