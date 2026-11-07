#!/usr/bin/env python3
"""SkillHandoffBench Phase 2 · Gate D：给官方 `script/eval_policy.py` 打**被动记录** hooks。

这是对官方源码的第 3 个最小 patch（`docs/patches/004_eval_trace_hooks.patch`）。
要求与保证：
  - 每次插入都是**一条 `shb_trace.hook(...)` 调用**，不改变任何控制流、不改变任何变量；
  - `shb_trace` 在 `SHB_TRACE_JSONL` 未设置时 `hook()` 立刻 return → **零行为差异**；
  - 幂等：已打过就跳过（用 `patch 004` 标记检测）；
  - 打完自动 `git diff` 落盘 patch 文件，便于审计。

用法（在 RoboCombine 仓库根目录或任意位置）：
    python scripts/apply_trace_patch.py --repo /scratch/lijh/SkillHandoffBench/third_party/RoboCombine \
        --patch-out docs/patches/004_eval_trace_hooks.patch
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

MARK = "[SkillHandoffBench patch 004]"

# (anchor, replacement) —— 每个 anchor 必须在文件中恰好出现一次
EDITS = [
    (
        "from handoff_eval.real_switch_runtime import XVLARealSwitchSession",
        "from handoff_eval.real_switch_runtime import XVLARealSwitchSession\n"
        "try:  # " + MARK + " 被动状态记录（未设置 SHB_TRACE_JSONL 时零开销）\n"
        "    import shb_trace\n"
        "except ImportError:  # 没把 scripts/ 放进 PYTHONPATH 时保持官方行为不变\n"
        "    class _NoTrace:\n"
        "        @staticmethod\n"
        "        def hook(*args, **kwargs):\n"
        "            return None\n"
        "    shb_trace = _NoTrace()",
    ),
    (
        "        reset_event = controller.begin_episode(env=task_env, state=episode_state, "
        "initial_instruction=initial_instruction, step_count=0)",
        "        reset_event = controller.begin_episode(env=task_env, state=episode_state, "
        "initial_instruction=initial_instruction, step_count=0)\n"
        "        shb_trace.hook('episode_start', task_env=task_env, model=model, state=episode_state, "
        "seed=now_seed, subtask_instructions=subtask_instructions, initial_instruction=initial_instruction)",
    ),
    (
        "            observation = task_env.get_obs()\n"
        "            eval_func(task_env, model, observation)",
        "            observation = task_env.get_obs()\n"
        "            shb_trace.hook('pre_action', task_env=task_env, model=model, state=episode_state)  # " + MARK + "\n"
        "            eval_func(task_env, model, observation)",
    ),
    (
        "            step_count = task_env.take_action_cnt\n"
        "            if hse_variant == ORDERED_HSE:",
        "            step_count = task_env.take_action_cnt\n"
        "            shb_trace.hook('post_action', task_env=task_env, model=model, state=episode_state)  # " + MARK + "\n"
        "            if hse_variant == ORDERED_HSE:",
    ),
    (
        "                        subtask_completion_steps[i] = step_count",
        "                        subtask_completion_steps[i] = step_count\n"
        "                        shb_trace.hook('cue', task_env=task_env, model=model, state=episode_state, "
        "stage_idx=i, completion_step=step_count)  # " + MARK + " 完成信号(=Oracle 切换信号)首次为真",
    ),
    (
        "                            if switch_event is not None:\n"
        "                                print(\n"
        "                                    f\"Oracle HSE -> stage {switch_event['to_subtask_idx'] + 1} at step {step_count}\",\n"
        "                                    flush=True,\n"
        "                                )",
        "                            if switch_event is not None:\n"
        "                                print(\n"
        "                                    f\"Oracle HSE -> stage {switch_event['to_subtask_idx'] + 1} at step {step_count}\",\n"
        "                                    flush=True,\n"
        "                                )\n"
        "                                shb_trace.hook('switch', task_env=task_env, model=model, state=episode_state, "
        "mechanism='oracle_immediate', switch_event=switch_event)  # " + MARK,
    ),
    (
        "            controller.flush_pending_switch(\n"
        "                env=task_env, model=model, state=episode_state, step_count=step_count,\n"
        "            )",
        "            _shb_deferred_switch = controller.flush_pending_switch(\n"
        "                env=task_env, model=model, state=episode_state, step_count=step_count,\n"
        "            )\n"
        "            if _shb_deferred_switch is not None:\n"
        "                shb_trace.hook('switch', task_env=task_env, model=model, state=episode_state, "
        "mechanism='deferred_after_chunk', switch_event=_shb_deferred_switch)  # " + MARK,
    ),
    (
        "        actual_steps = task_env.take_action_cnt\n"
        "        subtask_stats[\"episode_steps\"].append(actual_steps)",
        "        actual_steps = task_env.take_action_cnt\n"
        "        shb_trace.hook('episode_end', task_env=task_env, model=model, state=episode_state, "
        "success=succ, total_steps=actual_steps, subtask_completion_steps=list(subtask_completion_steps), "
        "switch_events=list(episode_switch_events))  # " + MARK + "\n"
        "        subtask_stats[\"episode_steps\"].append(actual_steps)",
    ),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="RoboCombine 仓库根目录")
    ap.add_argument("--patch-out", default=None, help="把 git diff 写到这个文件")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    target = repo / "script" / "eval_policy.py"
    if not target.is_file():
        print(f"NOT FOUND: {target}")
        return 2
    src = target.read_text(encoding="utf-8")

    if MARK in src:
        print("already patched (marker found); nothing to do")
    else:
        for anchor, repl in EDITS:
            n = src.count(anchor)
            if n != 1:
                print(f"ANCHOR ERROR: expected exactly 1 occurrence, got {n}:\n---\n{anchor[:200]}\n---")
                return 3
            src = src.replace(anchor, repl, 1)
        target.write_text(src, encoding="utf-8")
        print(f"patched {target}")

    if args.patch_out:
        out = Path(args.patch_out)
        if not out.is_absolute():
            out = Path.cwd() / out          # 相对当前工作目录，而不是仓库目录
        out.parent.mkdir(parents=True, exist_ok=True)
        diff = subprocess.run(["git", "diff", "--", "script/eval_policy.py"], cwd=repo,
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace").stdout or ""
        # 同时保存"包含本次 patch 的全仓库 diff"，便于一次性审计
        out.write_text(diff, encoding="utf-8")
        print(f"wrote diff -> {out} ({len(diff)} bytes)")

    # 语法自检
    import py_compile
    try:
        py_compile.compile(str(target), doraise=True)
        print("syntax OK")
    except py_compile.PyCompileError as exc:
        print("SYNTAX ERROR:", exc)
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
