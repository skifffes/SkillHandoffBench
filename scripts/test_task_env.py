#!/usr/bin/env python3
"""SkillHandoffBench: 只验证**仿真栈**能否跑通一个两阶段任务（不含策略、不算评测结果）。

它复刻 `script/eval_policy.py::main()` 的 arg 装配，然后：
  setup_demo → play_once()（官方专家脚本，会调用 mplib/curobo 规划）→ check_success() → close_env()

用途：在花 30 分钟跑 Motus 之前，先证明 assets / embodiment / 渲染 / 规划器 / 物理都正常。
它**不产生任何评测成绩**，输出只写日志（logs/sim_smoke_<task>.log）。

用法（在 RoboCombine 仓库根目录）：
  python ../../scripts/test_task_env.py living_room_tidy_2tasks
"""
from __future__ import annotations

import os
import sys
import time
import traceback

import yaml

REPO = os.environ.get("ROBOCOMBINE_ROOT", os.getcwd())
sys.path.insert(0, REPO)
os.chdir(REPO)
sys.path.append("./")
sys.path.append("./policy")
sys.path.append("./description/utils")
sys.path.append("./script")

import eval_policy as ep  # noqa: E402
from envs import CONFIGS_PATH  # noqa: E402


def build_args(task_name: str, task_config: str = "robocombine_eval") -> dict:
    with open(f"./task_config/{task_config}.yml", "r", encoding="utf-8") as handle:
        args = yaml.safe_load(handle.read())
    args["task_name"] = task_name
    args["task_config"] = task_config
    args["policy_name"] = "sim_only"
    embodiment_type = args.get("embodiment")
    with open(os.path.join(CONFIGS_PATH, "_embodiment_config.yml"), "r", encoding="utf-8") as handle:
        embodiment_types = yaml.safe_load(handle.read())

    def get_embodiment_file(name):
        robot_file = embodiment_types[name]["file_path"]
        if robot_file not in (None, ""):
            return robot_file
        from envs import asset_path
        return str(asset_path("embodiments", name))

    with open(CONFIGS_PATH + "_camera_config.yml", "r", encoding="utf-8") as handle:
        camera_config = yaml.safe_load(handle.read())
    head_camera_type = args["camera"]["head_camera_type"]
    args["head_camera_h"] = camera_config[head_camera_type]["h"]
    args["head_camera_w"] = camera_config[head_camera_type]["w"]
    args["left_robot_file"] = get_embodiment_file(embodiment_type[0])
    args["right_robot_file"] = get_embodiment_file(embodiment_type[0])
    args["dual_arm_embodied"] = True
    args["left_embodiment_config"] = ep.get_embodiment_config(args["left_robot_file"])
    args["right_embodiment_config"] = ep.get_embodiment_config(args["right_robot_file"])
    args["render_freq"] = 0
    args["eval_video_log"] = False
    return args


def main() -> int:
    task_name = sys.argv[1] if len(sys.argv) > 1 else "living_room_tidy_2tasks"
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 100042
    t0 = time.time()
    print(f"[sim_smoke] task={task_name} seed={seed} repo={REPO}", flush=True)
    print(f"[sim_smoke] assets={os.environ.get('ROBOCOMBINE_ASSETS_DIR')}", flush=True)
    args = build_args(task_name)
    env_cls = ep.class_decorator(task_name)
    env = env_cls  # class_decorator 返回的是**实例**，不是类（Phase 1 踩过一次）
    try:
        env.setup_demo(now_ep_num=0, seed=seed, is_test=True, **args)
        print(f"[sim_smoke] setup_demo OK in {time.time()-t0:.1f}s; subtasks={len(getattr(env, 'subtask_completed', []))}", flush=True)
        t1 = time.time()
        info = env.play_once()
        print(f"[sim_smoke] play_once OK in {time.time()-t1:.1f}s", flush=True)
        plan_ok = bool(getattr(env, "plan_success", False))
        strict_ok = bool(env.check_success())
        print(f"[sim_smoke] plan_success={plan_ok} strict_check_success={strict_ok}", flush=True)
        print(f"[sim_smoke] subtask_completed={getattr(env, 'subtask_completed', None)}", flush=True)
        obs = env.get_obs()
        rgb = obs["observation"]["head_camera"]["rgb"]
        print(f"[sim_smoke] obs keys={list(obs.keys())} head_rgb={rgb.shape} {rgb.dtype} mean={float(rgb.mean()):.2f}", flush=True)
        print(f"[sim_smoke] total {time.time()-t0:.1f}s", flush=True)
        return 0 if (plan_ok and strict_ok) else 3
    except Exception as exc:  # noqa: BLE001
        print(f"[sim_smoke] FAILED: {type(exc).__name__}: {exc}", flush=True)
        traceback.print_exc()
        return 1
    finally:
        try:
            env.close_env()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    sys.exit(main())
