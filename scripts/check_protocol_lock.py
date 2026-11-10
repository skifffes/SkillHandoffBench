#!/usr/bin/env python3
"""校验 configs/robocombine_public_protocol_lock.yaml 与本地代码/文件是否仍然一致。

只读、纯 CPU、不联网。设计成"锁文件 → 代码"的回归检查：
任何人改了 spec / scene yml / 关键参数而没更新锁文件，`python scripts/check_protocol_lock.py`
会以非零退出码报出来。

用法：
  python scripts/check_protocol_lock.py [--root .] [--lock configs/robocombine_public_protocol_lock.yaml]
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import sys

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


def sha16(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


class Report:
    def __init__(self):
        self.rows = []

    def add(self, name, ok, detail=""):
        self.rows.append((name, bool(ok), detail))
        return ok

    def ok(self):
        return all(r[1] for r in self.rows)

    def dump(self):
        for name, ok, detail in self.rows:
            print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  -- {detail}" if detail else ""))
        n_fail = sum(1 for r in self.rows if not r[1])
        print(f"\n{len(self.rows)} checks, {n_fail} failed")
        return 0 if n_fail == 0 else 1


def load_lock(path):
    if yaml is None:
        raise SystemExit("需要 pyyaml：pip install pyyaml")
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--lock", default="configs/robocombine_public_protocol_lock.yaml")
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    lock = load_lock(os.path.join(root, args.lock))
    rep = Report()

    repo = os.path.join(root, "third_party", "RoboCombine")

    # 1) spec / scene yml 指纹
    spec = os.path.join(repo, lock["task_split"]["spec"])
    rep.add("spec 存在", os.path.exists(spec), spec)
    if os.path.exists(spec):
        rep.add("spec sha16 匹配", sha16(spec) == lock["task_split"]["sha256_16"], sha16(spec))
        data = json.load(open(spec, encoding="utf-8"))
        rep.add("任务数 = 19", len(data["tasks"]) == lock["task_split"]["task_count"], str(len(data["tasks"])))
        rep.add("全部 stage_count = 2", all(t["stage_count"] == 2 for t in data["tasks"]))
        rep.add("spec 默认 episodes = 5（必须被 --episodes 覆盖）",
                int(data["default_episodes"]) == 5, str(data.get("default_episodes")))
        rep.add("spec 默认 max_steps = 1500",
                int(data["default_max_steps_per_episode"]) == lock["protocol"]["max_steps_per_episode"])

    scene = os.path.join(repo, lock["scene"]["task_config"])
    rep.add("scene yml 存在", os.path.exists(scene), scene)
    if os.path.exists(scene) and yaml is not None:
        rep.add("scene yml sha16 匹配", sha16(scene) == lock["scene"]["sha256_16"], sha16(scene))
        cfg = yaml.safe_load(open(scene, encoding="utf-8"))
        dr = cfg.get("domain_randomization", {})
        for key, want in (("random_background", False), ("cluttered_table", False),
                          ("random_light", False)):
            rep.add(f"scene.{key} == {want}", bool(dr.get(key)) is want, str(dr.get(key)))
        rep.add("scene.clean_background_rate == 1", int(cfg.get("domain_randomization", {}).get("clean_background_rate", 0)) == 1)

    # 2) README 里关于 clear-cache 的论文声明（防止上游改文档）
    readme = os.path.join(repo, "README.md")
    if os.path.exists(readme):
        txt = open(readme, encoding="utf-8").read()
        rep.add("README 声明 '--clear-cache false' 为论文设置",
                "paper's chunk-preserving setting" in txt and "--clear-cache false" in txt)

    # 3) runner 默认值（必须知道它是 true，我们的命令必须显式 false）
    rs = os.path.join(repo, "handoff_eval", "runner", "run_split.py")
    if os.path.exists(rs):
        src = open(rs, encoding="utf-8").read()
        rep.add("run_split 默认 clear-cache = true（因此必须显式覆盖）",
                re.search(r"--clear-cache'.{0,80}default='true'", src) is not None)
        rep.add("run_split 会透传 --clear_cache", "'--clear_cache'" in src)

    # 4) eval_policy 里专家筛选与 ordered 语义的关键锚点
    ep = os.path.join(repo, "script", "eval_policy.py")
    if os.path.exists(ep):
        src = open(ep, encoding="utf-8").read()
        rep.add("存在专家筛选 continue（skip 不计数）",
                "if not (task_env.plan_success and task_env.check_success())" in src)
        rep.add("存在 skip_successful 默认 True", "skip_successful=True" in src)
        rep.add("存在 sequential 判定（s1_step<=s2_step）", "is_sequential" in src)
    sm = os.path.join(repo, "handoff_eval", "summary", "summarize_split.py")
    if os.path.exists(sm):
        src = open(sm, encoding="utf-8").read()
        rep.add("summarize_split 用 sequential 计算 sr_ordered", "sequential" in src and "sr_ordered" in src)

    # 5) chunk-preserving 的执行锚点
    dp = os.path.join(repo, "policy", "Motus", "deploy_policy.py")
    if os.path.exists(dp):
        src = open(dp, encoding="utf-8").read()
        rep.add("deploy_policy 有 action_cache 与 prepare_instruction_switch",
                "action_cache" in src and "prepare_instruction_switch" in src)
    hse = os.path.join(repo, "handoff_eval", "hse.py")
    if os.path.exists(hse):
        src = open(hse, encoding="utf-8").read()
        rep.add("hse.flush_pending_switch 仅在缓存为空时切换",
                "flush_pending_switch" in src and "len(getattr(model" in src)

    # 6) 已有运行命令必须带 --episodes 20 / --clear-cache false
    cmds = glob.glob(os.path.join(root, "results", "paper_table1", "**", "command.sh"), recursive=True)
    if cmds:
        bad_ep = [c for c in cmds if "--episode_num 20" not in open(c, encoding="utf-8").read()]
        bad_cc = [c for c in cmds if "--clear_cache false" not in open(c, encoding="utf-8").read()]
        # probe 是 5 episodes，属于允许的例外
        bad_ep = [c for c in bad_ep if "--episode_num 5" not in open(c, encoding="utf-8").read()
                  and "--episode_num 3" not in open(c, encoding="utf-8").read()]
        rep.add(f"全部 command.sh 带 --episode_num 20 或显式 5/3（共 {len(cmds)} 个）", not bad_ep, str(bad_ep[:2]))
        rep.add(f"全部 command.sh 带 --clear_cache false（共 {len(cmds)} 个）", not bad_cc, str(bad_cc[:2]))
    else:
        rep.add("找到 command.sh", False, "results/paper_table1 下没有 command.sh")

    # 7) 本地 checkpoint（若存在则校验大小；不重算 16GB 哈希，用锁文件值对照已知记录）
    ckpt = lock["model"].get("local_path")
    if ckpt and os.path.exists(ckpt):
        f = os.path.join(ckpt, lock["model"]["file"])
        if os.path.exists(f):
            rep.add("checkpoint 大小匹配", os.path.getsize(f) == lock["model"]["size_bytes"],
                    str(os.path.getsize(f)))
    return rep.dump()


if __name__ == "__main__":
    sys.exit(main())
