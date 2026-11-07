# 08 · 交接状态被动采样仪器（Gate D）

运行时间：2026-11-07 14:32–15:20 CST。**结论：PASS（被动性已证明）**。

---

## 1. 一句话结论

在同一任务、同一 seed（`living_room_tidy_2tasks` / `4300000`）上，
**不记录 / 只记 action / 记全部状态** 三次运行的
**逐 episode 统计、task.log（388 行）、173 条 action 序列全部逐位相同**，
因此本仪器是**被动的**，可以用于后续 B4–B7 的受控实验。

---

## 2. 实现（不改控制流）

| 组件 | 作用 |
| --- | --- |
| `scripts/shb_trace.py` | 记录器；`hook()` 在 `SHB_TRACE_JSONL` 未设置时**立即 return** |
| `docs/patches/004_eval_trace_hooks.patch` | 在 `script/eval_policy.py` 插入 8 条 `shb_trace.hook(...)`（纯调用，不改任何变量/控制流） |
| `scripts/apply_trace_patch.py` | 幂等打 patch + 语法自检 + 落盘 diff |
| `scripts/analyze_trace.py` | JSONL → `*_handoff_events.csv`（按 A–E 语义对齐） |
| `scripts/run_trace_ab.sh` / `compare_trace_ab.py` | 三次运行 + 等价性判定 |

**动作序列怎么来的**：`install_action_hook()` 把 `task_env.take_action` 包一层，
先记录**原始 action** 再原样调用原函数（不修改、不替换、不重排）。

**patch 的关键安全设计**：
```python
try:  # [SkillHandoffBench patch 004]
    import shb_trace
except ImportError:      # 没把 scripts/ 放进 PYTHONPATH 时保持官方行为不变
    class _NoTrace:
        @staticmethod
        def hook(*args, **kwargs): return None
    shb_trace = _NoTrace()
```

---

## 3. 事件语义（**cue ≠ switch**，本轮已实测确认）

```
cue     完成信号（subtask_completed[i]）第一次为真的那一步
switch  控制器真正把指令换掉的那一步
```

在 `--clear-cache false` 下，`HSE._switch_to_next_stage` 会因为 `action_cache` 非空而**挂起切换**，
真正的切换发生在之后某一步的 `flush_pending_switch()`。本轮实测：

| 字段 | 值 | 含义 |
| --- | --- | --- |
| `cue_step` | **51** | 第一阶段完成信号触发 |
| `switch_step` | **64** | 真正换指令 |
| `cue_to_switch_steps` | **13** | 中间隔了 13 步 |
| `action_cache_len` @cue | **13** | 触发瞬间还有 13 个 A 技能的动作没执行 |
| `action_cache_len` @switch | **0** | 缓存排空后才切换 |
| `mechanism` | `deferred_after_chunk` | 不是 immediate |
| `pre_switch_action_step` / `post_switch_action_step` | 63 / 64 | 切换前最后一个 action 在第 63 步，切换后第一个在第 64 步 |

> 这就是"**必须区分 cue 状态与 B 技能真正开始执行的状态**"的直接证据：
> 两者相差 13 步，而且这 13 步里机器人还在执行 **A 技能**的动作。

---

## 4. 记录字段（本轮实际写出的内容）

| 类别 | 字段 | 本轮是否可用 |
| --- | --- | --- |
| 身份/时间 | `seq, event, episode_idx, seed, step(take_action_cnt), t_wall` | ✅ |
| 关节 | `joints.{left,right}.{names, qpos, qvel, arm_joint_indices}`（从 articulation 读；`qpos/qvel` 长度 38，`arm_joint_indices=[6,14,18,22,26,30]`） | ✅ |
| 末端位姿 | `ee_pose.{left,right}.{p, q}`（7 维，含四元数） | ✅ |
| 夹爪 | `gripper.{left,right}` | ✅（cue: 0.980 / 0.432 → switch: 0.988 / 1.000） |
| 物体 6D | `objects.<attr>.{p,q}`（wall/table/cup/coaster/fan/fan_pad 等） | ✅ |
| 接触 | `contacts` | ⚠️ 默认关闭（`SHB_TRACE_CONTACTS=1` 才统计 `scene.get_contacts()` 数量），本轮为 `null` |
| 指令/阶段 | `instruction, stage_idx, subtask_completed[], pending_switch, switch_events_so_far` | ✅ |
| 缓存 | `action_cache_len` | ✅ |
| 观测引用 | `render_rgb.{sha1,nbytes,shape}`（对 `task_now_obs` 取哈希，不触发新渲染） | ✅（cue `a5a2c981…` → switch `2234647f…`） |
| 事件专属 | `cue.stage_idx/completion_step`、`switch.mechanism/switch_event`、`episode_end.success/total_steps` | ✅ |

事件计数（`full.jsonl`，524 条）：`episode_start 1 / pre_action 173 / action 173 / post_action 173 / cue 2 / switch 1 / episode_end 1`。

---

## 5. A/B 无干预验证（3 次运行，同任务同 seed）

| 运行 | 环境变量 | 记录 |
| --- | --- | --- |
| `ab_off` | 无 | 无 |
| `ab_actions_only` | `SHB_TRACE_JSONL=…` + `SHB_TRACE_ACTIONS_ONLY=1` | 只记 action |
| `ab_full` | `SHB_TRACE_JSONL=…` | action + 全状态 |

| 检查 | 结果 |
| --- | --- |
| stats 逐位相同（seed / success / steps / s1_step / s2_step / switch_step） | ✅ **三次全为 `4300000 / True / 173 / 51 / 125 / 64`** |
| task.log 归一化后逐行相同 | ✅ **388 行完全一致**（off vs actions_only vs full） |
| action 序列相同 | ✅ **173 vs 173，max_abs_diff = 0.0**（tol 1e-9） |
| trace 代码无 RNG | ✅ 静态扫描无 `np.random` / `random.*` / `torch.rand*` |

**verdict: PASS**（`results/phase2/trace/ab_comparison.json`）。

> 三次运行与 Phase 1 的同 seed 结果也完全一致（173 步、s1@51、s2@125、switch@64），
> 说明这条 episode 是可重复的基准。

---

## 6. 与"运行失败"无关：退出码 -11 的说明

所有 Phase 2 子进程（Gate B/C/D 共 9 个被记录的 `eval_policy`）都以 **`code=-11`（SIGSEGV）** 结束，
但：

- `stats=yes`，`evaluation_statistics.json` 内容完整；
- 任务目录里 **`_result.txt` 存在**（它是 `main()` 最后一行才写的）；
- `task.log` 的最后一行就是第 173 步的终局判定。

→ 段错误发生在 **`main()` 返回之后的解释器退出阶段**（torch + SAPIEN + CuRobo 的析构顺序问题），
**不影响任何指标**。`run_split` 因此把整个 run 的退出码记成 1（`failed=any(exit_code!=0)`），
这是**记账层面的假失败**，不是 rollout 失败。docs/06 §3、docs/07 §3 的所有数字都取自
`evaluation_statistics.json`，与退出码无关。

---

## 7. 修正记录（诚实留痕）

| # | 问题 | 修正 |
| --- | --- | --- |
| 1 | `SHB_TRACE_ACTIONS_ONLY=1` 时把 action 也跳过了 → `action_count_equal 0 vs 173` | 改成动作在两种模式下都记；重跑后 173 vs 173，`max_abs_diff=0.0` |
| 2 | `Robot.get_*_ee_pose()` 返回的是 **7 维 list**，不是 `sapien.Pose` → 首轮 `ee_pose` 全 unreadable | 兼容 list/ndarray/Pose；现在 `ee_pose.left.p/q` 正常 |
| 3 | 逐关节 `joint.get_qpos()` 在 SAPIEN 3 不存在（AttributeError） | 改为从 articulation 读：`robot.{left,right}_entity.get_qpos()/get_qvel()`；现在 `qpos/qvel` 各 38 维 |

这三条都写在这里，因为"仪器是否真的采到数据"必须可审计，不能只看脚本存在。

---

## 8. 可以拿它做什么 / 不能做什么

**能做**：
- 在 B4–B7 里，对**同一个 cue 时刻**记录交接状态（关节/末端/物体/夹爪/缓存余量），
  从而区分"交接状态不同"与"下游能力不足"；
- 复盘失败 episode：例如 `docs/07` 里 `desk_arrange` 4300003 的"切换后 1458 步无进展"，
  可以用同一套字段在下一轮直接对比"成功交接"与"失败交接"的状态差异。

**不能做**（本轮明确未做）：
- 不能用它修改状态/动作、提前触发切换、或调用额外规划器；
- 不能把"接触状态"当作已采集（默认关闭，需要显式打开且会变慢）。
