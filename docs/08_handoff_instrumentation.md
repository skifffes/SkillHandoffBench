# 08 · 交接状态被动采样仪器（Gate D）

> 状态：**已实现并通过本地自测**；服务器上的 A/B 验证将在 Gate C 之后执行。
> 本文件先固定事件语义、记录字段与"无干预"的判定标准；数据跑完后填入。

---

## 1. 目标与边界

**只做 instrumentation**：在官方评测流程里**只读地**记录物理状态，用于以后回答
"这个失败到底是不是交接状态造成的"。

**不做**：运动规划器、状态修改、动作注入、提前切换、额外 reset。
若不能证明"被动"，则本文件只能写 **PARTIAL**（任务书 §五 明确要求）。

---

## 2. 官方执行顺序（先审计，再打点）

来自 `script/eval_policy.py` 主循环（行号对应 commit `df237b2`）：

```
step N:  observation = task_env.get_obs()
         eval_func(task_env, model, observation)      # 内部：取缓存/推理 → task_env.take_action(action)
             └─ take_action(): 一个 action 内部会多次 scene.step()，每次都 check_success()
         if task_env.subtask_completed[i] and subtask_completion_steps[i] is None:
                 subtask_completion_steps[i] = step_count      ← ★ 事件 A（cue）
                 if ORACLE_HSE and i == current_stage_idx:
                     controller.handle_oracle_hse(...)          ← 可能"立即切换"
         controller.flush_pending_switch(...)                   ← 也可能"chunk 排空后切换"
```

**关键**：`--clear-cache false` 时，`handle_oracle_hse` 里的 `_switch_to_next_stage` 会把切换
**挂起**（`state.pending_switch`），真正的切换发生在之后某一步的 `flush_pending_switch`。
所以：

- **A. cue** = 完成信号第一次为真的那一步；
- **B. chunk 排空** = 切换前最后一个被执行的 action；
- **C. 切换后第一次推理前** = switch 事件之后第一条 `pre_action`；
- **D. B 技能首条动作执行** = switch 之后第一条 `action` 记录；
- **E. episode 结束** = `episode_end`。

**A ≠ C**：Phase 1 实测 cue 51 → switch 64（差 13 步）；5 个 episode 差值 1–15 步。

---

## 3. 实现方式（不改控制流）

| 组件 | 作用 |
| --- | --- |
| `scripts/shb_trace.py` | 记录器：`hook()` 在 `SHB_TRACE_JSONL` 未设置时**立即 return** |
| `docs/patches/004_eval_trace_hooks.patch` | 在 `eval_policy.py` 插入 8 条 `shb_trace.hook(...)`（纯调用，不改变量/控制流） |
| `scripts/apply_trace_patch.py` | 幂等打 patch + 语法自检 + 落盘 diff |
| `scripts/analyze_trace.py` | JSONL → `handoff_events.csv`（按 A–E 语义对齐） |
| `scripts/run_trace_ab.sh` | 同 seed 跑 off / actions_only / full 三次 |
| `scripts/compare_trace_ab.py` | 判定三次运行是否等价 |

**动作序列是怎么拿到的**：`shb_trace.install_action_hook()` 把 `task_env.take_action` 包一层，
先记录**原始 action 对象**再原样调用原函数 —— 不修改、不替换、不重排。

---

## 4. 记录字段

| 类别 | 字段 |
| --- | --- |
| 时间/身份 | `seq`（全局序号）、`event`、`episode_idx`、`seed`、`step`（`take_action_cnt`）、`t_wall` |
| 机器人 | `joints.{left,right}.{names,qpos,qvel}`、`ee_pose.{left,right}.{p,q}`、`gripper.{left,right}` |
| 物体 | `objects.<attr>.{p,q,v}`（只读 `get_pose()`/`get_velocity()`） |
| 接触 | `contacts`（默认 null；`SHB_TRACE_CONTACTS=1` 才统计 `scene.get_contacts()` 数量） |
| 指令/阶段 | `instruction`、`stage_idx`、`subtask_completed[]`、`pending_switch`、`switch_events_so_far` |
| 缓存 | `action_cache_len` |
| 观测引用 | `render_rgb.{sha1,nbytes,shape}`（对 `task_env.now_obs` 取哈希，**不触发新渲染**） |
| 事件专属 | `cue`: `stage_idx`/`completion_step`；`switch`: `mechanism`/`switch_event`；`episode_end`: `success`/`total_steps` |

---

## 5. A/B 无干预验证（三次运行，同任务同 seed）

| 运行 | 环境变量 | 记录内容 |
| --- | --- | --- |
| R1 `ab_off` | 无 | 无（基线） |
| R2 `ab_actions_only` | `SHB_TRACE_JSONL=…/actions_only.jsonl`、`SHB_TRACE_ACTIONS_ONLY=1` | 只记 action |
| R3 `ab_full` | `SHB_TRACE_JSONL=…/full.jsonl` | action + 全部状态 |

判定（`scripts/compare_trace_ab.py`）：

1. R1/R2/R3 的 `evaluation_statistics` 关键字段（seed / success / total_steps / s1_step / s2_step / switch_step）**逐位相同**；
2. 三份 `task.log` **归一化后逐行相同**（去 `step_time=`）；
3. R2 与 R3 的 action 序列**逐元素相同**（容差见 `--tol`，默认 0）；
4. 静态检查：`shb_trace.py` 不含任何 RNG 调用。

任一不满足 → 本文件标 **PARTIAL**，不得声称"已建立无干预采样接口"。

---

## 6. 结果（跑完后填）

### 6.1 A/B 等价性

| 检查 | 结果 |
| --- | --- |
| stats 逐位相同 | pending |
| task.log 归一化逐行相同 | pending |
| action 序列相同 | pending |
| trace 代码无 RNG | pending |

### 6.2 交接事件表（示例结构）

`results/phase2/trace/full_handoff_events.csv` 的列包括：
`episode_idx, seed, mechanism, from_stage, to_stage, cue_step, switch_step, cue_to_switch_steps,
pre_switch_action_step, post_switch_action_step, post_switch_pre_action_step,
cue_gripper_left/right, switch_gripper_left/right, cue_action_cache_len, switch_action_cache_len,
cue_render_sha1, switch_render_sha1, cue_ee_pose_left, switch_ee_pose_left, cue_objects, switch_objects`

---

## 7. 结论（跑完后填）
