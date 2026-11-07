#!/usr/bin/env python3
"""SkillHandoffBench Phase 2 · Gate D：**被动**状态记录器。

设计原则（对应任务书 §五）
  1. 只读：只调用 get_pose()/get_qpos()/get_qvel()/len(cache) 这类查询，不写回、不重置、不推进仿真；
  2. 不参与控制：不返回任何值给调用方，不改变 action、不提前切换、不调用规划器；
  3. 零开销保护：`SHB_TRACE_JSONL` 未设置时，`hook()` 立即 return（唯一开销是一次布尔判断）；
  4. 事件与时间步：每条记录都带 `episode_idx / seed / step(=take_action_cnt) / seq`；
  5. 不在 `hook()` 里调用 `get_obs()` 或 `get_contacts()` 以外的重活：
     - 相机只对 `task_env.now_obs`（上一步已算好的观测）取哈希，不触发新渲染；
     - 接触查询默认关闭，`SHB_TRACE_CONTACTS=1` 才做（因为 `scene.get_contacts()` 较慢）。

事件语义（由 eval_policy 打点，见 docs/patches/004_eval_trace_hooks.patch）
  episode_start   episode 开始（setup_demo 之后、策略执行之前）
  cue             某个子任务的完成信号第一次为真（= Oracle HSE 的切换信号）
  switch          控制器真正执行了指令切换（可能是 immediate，也可能是 chunk 排空后的 deferred）
  pre_action      每次调用策略/执行 action 之前
  post_action     每次 action 执行完之后
  episode_end     episode 结束（成功/超时/失败）

**注意**：`cue` 与 `switch` 是两个不同事件；在 `--clear-cache false` 下它们必然不同步
（Phase 1 实测 cue 51 → switch 64）。分析时必须分开，见 scripts/analyze_trace.py。
"""
from __future__ import annotations

import hashlib
import json
import os
import time

_TRACE_PATH = os.environ.get("SHB_TRACE_JSONL") or ""
ENABLED = bool(_TRACE_PATH)
_ACTIONS_ONLY = os.environ.get("SHB_TRACE_ACTIONS_ONLY", "0") in {"1", "true", "True"}
_WITH_CONTACTS = os.environ.get("SHB_TRACE_CONTACTS", "0") in {"1", "true", "True"}
_MAX_OBJ = int(os.environ.get("SHB_TRACE_MAX_OBJECTS", "12"))

_seq = 0
_episode_idx = -1
_episode_seed = None


def _hash_rgb(task_env):
    """对最近一次已计算的 head 相机帧取哈希；不触发渲染。"""
    try:
        obs = getattr(task_env, "now_obs", None) or {}
        rgb = obs.get("observation", {}).get("head_camera", {}).get("rgb")
        if rgb is None:
            return None
        arr = rgb if isinstance(rgb, (bytes, bytearray)) else memoryview(rgb).tobytes()
        return {"sha1": hashlib.sha1(arr).hexdigest(), "nbytes": len(arr), "shape": list(rgb.shape)}
    except Exception:
        return None


def _joint_state(robot):
    """SAPIEN 3 里 qpos/qvel 挂在 **articulation** 上（robot.left_entity.get_qpos()），
    单个 joint 对象没有 get_qpos —— 这里按实体的方式读。"""
    out = {}
    for side in ("left", "right"):
        joints = getattr(robot, f"{side}_arm_joints", None) or []
        ent = getattr(robot, f"{side}_entity", None)
        item = {}
        try:
            item["names"] = [j.get_name() for j in joints]
        except Exception as exc:
            item["names_error"] = f"{type(exc).__name__}: {exc}"
        try:
            item["qpos"] = [float(x) for x in ent.get_qpos()]
            item["qvel"] = [float(x) for x in ent.get_qvel()]
            item["n_entity_dof"] = len(item["qpos"])
        except Exception as exc:
            item["qpos_error"] = f"{type(exc).__name__}: {exc}"
        # 手臂 6 个关节的索引（与 names 对齐），方便下游只取手臂
        try:
            active = [j.get_name() for j in ent.get_active_joints()]
            item["active_joint_names"] = active
            item["arm_joint_indices"] = [active.index(n) for n in item.get("names", []) if n in active]
        except Exception:
            pass
        out[side] = item
    return out


def _ee_pose(robot):
    """Robot.get_*_ee_pose() 返回的是 **7 维 list**（xyz + quat），不是 sapien.Pose。
    这里同时兼容 list/ndarray/Pose 三种形态。"""
    out = {}
    for side in ("left", "right"):
        fn = getattr(robot, f"get_{side}_ee_pose", None)
        if fn is None:
            out[side] = {"error": "no accessor"}
            continue
        try:
            val = fn()
            if hasattr(val, "p") and hasattr(val, "q"):
                out[side] = {"p": [float(x) for x in val.p], "q": [float(x) for x in val.q]}
            else:
                arr = [float(x) for x in val]
                out[side] = {"p": arr[:3], "q": arr[3:7], "raw_len": len(arr)}
        except Exception as exc:
            out[side] = {"error": f"{type(exc).__name__}: {exc}"}
    return out


def _object_poses(task_env):
    """扫描 task_env 上的 sapien actor 属性（只读）。"""
    out = {}
    n = 0
    for name, val in list(vars(task_env).items()):
        if n >= _MAX_OBJ:
            break
        if name.startswith("_") or not hasattr(val, "get_pose") or not callable(getattr(val, "get_pose")):
            continue
        try:
            pose = val.get_pose()
            item = {"p": [float(x) for x in pose.p], "q": [float(x) for x in pose.q]}
            if hasattr(val, "get_velocity"):
                try:
                    v = val.get_velocity()
                    item["v"] = [float(x) for x in v]
                except Exception:
                    pass
            out[name] = item
            n += 1
        except Exception:
            continue
    return out


def _contacts(task_env):
    if not _WITH_CONTACTS:
        return None
    try:
        return int(len(task_env.scene.get_contacts()))
    except Exception:
        return None


def snapshot(task_env=None, model=None, state=None, action=None, **extra):
    rec = {
        "t_wall": round(time.time(), 6),
        "episode_idx": _episode_idx,
        "seed": _episode_seed,
        "step": int(getattr(task_env, "take_action_cnt", -1)) if task_env is not None else None,
    }
    if action is not None:
        # 动作序列在两种模式下都要记（actions_only 的用途就是比对动作序列）
        try:
            rec["action"] = [float(x) for x in list(action)]
        except Exception:
            rec["action"] = "unserializable"
    if task_env is not None:
        try:
            rec["instruction"] = task_env.get_instruction()
        except Exception:
            rec["instruction"] = None
        rec["subtask_completed"] = [bool(x) for x in getattr(task_env, "subtask_completed", [])]
        rec["eval_success"] = bool(getattr(task_env, "eval_success", False))
        rec["render_rgb"] = _hash_rgb(task_env)
        if not _ACTIONS_ONLY:
            robot = getattr(task_env, "robot", None)
            if robot is not None:
                rec["joints"] = _joint_state(robot)
                rec["ee_pose"] = _ee_pose(robot)
                rec["gripper"] = {
                    "left": float(getattr(robot, "left_gripper_val", float("nan"))),
                    "right": float(getattr(robot, "right_gripper_val", float("nan"))),
                }
            rec["objects"] = _object_poses(task_env)
            rec["contacts"] = _contacts(task_env)
    if model is not None and not _ACTIONS_ONLY:
        cache = getattr(model, "action_cache", None)
        rec["action_cache_len"] = len(cache) if cache is not None else None
    if state is not None:
        rec["stage_idx"] = int(getattr(state, "current_stage_idx", -1))
        rec["pending_switch"] = bool(getattr(state, "pending_switch", None) is not None)
        rec["switch_events_so_far"] = len(getattr(state, "switch_events", []) or [])
    if extra:
        rec.update(extra)
    return rec


def install_action_hook(task_env):
    """把 task_env.take_action 包一层记录动作，再原样返回。

    为什么这样做：策略产生的 action 只在 deploy_policy 内部可见，
    不改官方策略代码的前提下，唯一能拿到"真正下发的动作"的位置就是 take_action。
    包装只记录、不修改、不替换 action 对象。
    """
    if task_env is None or getattr(task_env, "_shb_trace_wrapped", False):
        return False
    orig = getattr(task_env, "take_action", None)
    if orig is None:
        return False
    import functools

    @functools.wraps(orig)
    def wrapped(action, *args, **kwargs):
        try:
            hook("action", task_env=task_env, action=action, action_type=kwargs.get("action_type", args[0] if args else "qpos"))
        except Exception:
            pass
        return orig(action, *args, **kwargs)

    task_env.take_action = wrapped
    task_env._shb_trace_wrapped = True
    return True


def hook(event, *, task_env=None, model=None, state=None, action=None, **extra):
    """由 eval_policy 调用的唯一入口。未启用时立即返回。"""
    if not ENABLED:
        return
    global _seq, _episode_idx, _episode_seed
    if event == "episode_start":
        _episode_idx += 1
        _episode_seed = extra.get("seed")
        install_action_hook(task_env)
    rec = snapshot(task_env=task_env, model=model, state=state, action=action, **extra)
    rec["seq"] = _seq
    rec["event"] = event
    _seq += 1
    try:
        with open(_TRACE_PATH, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        # 记录失败不能影响评测
        pass
