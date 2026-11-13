# 28 · 子任务完成事件的物理持续性诊断（Phase 4D）

日期：2026-11-13。范围：**4 个 interaction 任务 × 2 个固定 seed × oracle_hse，共 8 次带 trace 的 rollout**。
未训练、未换模型、未改判据、未做 Agent/PRTI/DeCo。

> **本文不声称解释了论文与本地的成功率差距。** 论文原始环境（任务代码版本、max steps、seed 规则、
> checkpoint revision）仍未对齐，本文件只回答一个局部问题：
> **"子任务完成标志触发之后，物理条件是否还成立？"**

---

## 1. 前置修正：`docs/27` 的统计定义

`docs/27` 把 `both_flags_true ∧ gripper_closed` 与 `ordered_true ∧ gripper_closed` 混在一列。
现按原始记录重算（18 任务里这 4 个，oracle/full 各 20 eps）：

| Task | Track | ordered | env 成功 | **both_flags ∧ grip_closed** | **ordered ∧ grip_closed** | 反序 env 成功 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| room_comfort | oracle | 13 | 0 | 13 | 13 | 0 |
| room_comfort | full | 12 | 2 | 10 | 10 | 0 |
| kitchen_switch | oracle | 11 | 1 | 11 | 10 | 0 |
| kitchen_switch | full | 0 | 0 | 0 | 0 | 0 |
| smart_home | oracle | 12 | 0 | 13 | 12 | 0 |
| smart_home | full | 8 | 0 | 10 | 8 | 0 |
| bakery_close | oracle | 17 | 7 | 10 | 10 | 0 |
| bakery_close | full | 5 | 0 | 5 | 5 | 0 |

两列差值 = "两标志都成立但**反序**且终局失败"的 episode 数
（room_comfort full 4 个、kitchen_switch oracle 1 个、smart_home oracle 1 个）。

---

## 2. Seed 选择（跑前登记）

原则：每个任务取 **一个"ordered 成功但 env 失败"案例** + **一个对照**（成功 或 S2 未触发）。

| Task | Seed | 历史类别（oracle） | 选择理由 |
| --- | --- | --- | --- |
| room_comfort | 4300001 | A：s1=52, s2=90, env 失败 | 核心现象（标志按序、env 失败） |
| room_comfort | 4300000 | C：s1=47, s2=None | 对照：S1 触发、S2 未触发 |
| kitchen_switch | 4300002 | A：s1=54, s2=118, env 失败 | 核心现象 |
| kitchen_switch | 4300029 | B：s1=46, s2=75，**成功@93** | 对照：同任务的成功轨迹 |
| smart_home | 4300017 | A：s1=35, s2=81, env 失败 | 核心现象 |
| smart_home | 4300011 | C：s1=36, s2=None | 对照：S2 未触发 |
| bakery_close | 4300006 | A：s1=38, s2=218, env 失败 | 核心现象 |
| bakery_close | 4300004 | B：s1=41, s2=64，**成功@140** | 对照：成功轨迹 |

**偏差登记（`NOT_RUN_AS_PLANNED`）**：`room_comfort` 的 **4300001 本次专家 demo 未通过**，
被官方循环跳过，实际跑了 **4300004**（历史类别 C：s1=36, s2=None）。
→ **room_comfort 没有拿到"A 类"（ordered 成功/env 失败）的 trace**，这是本轮的覆盖缺口；
也再次证实 `docs/27 §4.4` 指出的"专家校验不可复现"。

---

## 3. Trace 设计（被动，只读）

| 字段 | 内容 |
| --- | --- |
| `subtask_completed` | 每个采样点记录两个标志（官方 `task_env.subtask_completed`） |
| `articulated.switch` | **新增**：`qpos`、`qlimits`、`trigger_hi_minus_0.05`（是否满足官方判据）、`margin_to_hi` |
| `gripper.{left,right}` | 夹爪开度 |
| `objects` | 场景 actor 的 6D 位姿 |
| `ee_pose` / `joints` | 末端 7 维位姿 / 关节 qpos（38） |
| `eval_success`, `instruction`, `action_cache_len` | 官方终局标志、当前指令、缓存长度 |
| 事件 | `cue`（标志首次为真）、`switch`（真正换指令）、`episode_start/end` |

**采样时机**：`pre_action` / `post_action` 每个策略步各一条（与 `sr_ordered` 使用的
`subtask_completion_steps` 同一 `take_action_cnt` 口径）。官方 `check_success()` 在
`take_action()` 内部按物理子步调用，因此 trace 是**每个策略步采样一次**——若某事件
在 1 步内触发又回退，本 trace 会漏掉。这一点在第 8 节列为限制。

**非干预**：`hook()` 在未设 `SHB_TRACE_JSONL` 时立即 return；本次只读 `get_qpos/get_pose`，
不写任何仿真状态。行为不变性见第 7 节（8/8 复现历史轨迹）。

---

## 4. 结果总表（8 个 episode）

`thr` = `qlimits[0][1] − 0.05`（官方判据）；`below` = S2 触发后 qpos 低于 thr 的**唯一仿真步数**。

| Task | Seed | s1 | s2 | succ | switch@S2 | thr | min(after s2) | below | 终局夹爪 L/R | 判定 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| kitchen_switch | 4300002 | 54 | 118 | — | 0.3840 | 0.3340 | **−0.0000** | **1150** | 0.000 / 0.061 | **TRANSIENT_EVENT_CONFIRMED** |
| smart_home | 4300017 | 35 | 81 | — | 0.4147 | 0.3647 | **0.3473** | **1409** | 0.977 / 0.000 | **TRANSIENT_EVENT_CONFIRMED** |
| bakery_close | 4300006 | 38 | 218 | — | 0.3840 | 0.3340 | 0.3840 | **0** | 0.031 / 0.007 | **PERSISTENT_EVENT_BUT_TERMINAL_FAILURE** |
| room_comfort | 4300000 | 47 | — | — | — | — | — | — | 0.996 / 0.002 | OTHER_FAILURE（S2 未触发） |
| room_comfort | 4300004 | 36 | — | — | — | — | — | — | 0.988 / 0.008 | OTHER_FAILURE（S2 未触发） |
| smart_home | 4300011 | 36 | — | — | — | — | — | — | 0.000 / 1.000 | OTHER_FAILURE（S2 未触发，**第 448 步早停**） |
| kitchen_switch | 4300029 | 46 | 75 | **93** | 0.5411 | 0.4911 | 0.2472 | 15 | 0.984 / 0.803 | SUCCESS_CONTROL |
| bakery_close | 4300004 | 41 | 64 | **140** | 0.4147 | 0.3647 | 0.2138 | 28 | 0.977 / 0.801 | SUCCESS_CONTROL |

---

## 5. 逐条判读

### 5.1 `kitchen_switch` 4300002 —— **TRANSIENT_EVENT_CONFIRMED**

- S2 在 **step 118** 触发，此刻开关 `qpos = 0.3840 > thr = 0.3340`（合法触发）。
- 之后开关**回落到 ≈ 0.0000**，并在阈值以下持续 **1150 步**直到 episode 结束（1500）。
- 终局夹爪 L=0.000、R=0.061（均闭合）。
→ 标志记录的是**一次性推到位**，物理状态随后完全回退。任务从未真正"保持开启"。

### 5.2 `smart_home` 4300017 —— **TRANSIENT_EVENT_CONFIRMED**

- S2 在 **step 81** 触发，`qpos = 0.4147 > thr = 0.3647`。
- 之后回落到 **0.3473**，仅比阈值低 **0.0174 rad（≈1°）**，并保持 **1409 步**。
- 终局夹爪 L=0.977（开）、R=0.000（闭）。
→ 属于**边界型瞬态**：物理量只差 1°，但判据已不成立；同时右夹爪始终没张开。

### 5.3 `bakery_close` 4300006 —— **PERSISTENT_EVENT_BUT_TERMINAL_FAILURE**

- S2 在 **step 218** 触发，`qpos = 0.3840`；此后 **min 仍 = 0.3840，低于阈值的步数为 0**。
- 开关**全程保持**在阈值之上直到 1500。
- 但终局夹爪 L=0.031、R=0.007（均闭合）→ `success = all(flags) and gripper_open` 永远为 False。
→ 这是**干净的"终局条件失败"**案例：子任务真的完成了，失败在夹爪。

### 5.4 两个成功对照 —— **关键反例**

| Seed | 成功步 | 成功时 switch qpos | 当时 thr | 是否达标 |
| --- | ---: | ---: | ---: | --- |
| kitchen_switch 4300029 | 93 | **0.3647** | **0.4911** | ❌ **不达标** |
| bakery_close 4300004 | 140 | 0.3938 | 0.3647 | ✅ 达标 |

`kitchen_switch 4300029` 在**成功那一刻开关已经低于阈值**（0.3647 < 0.4911）——
因为 `success` 只看**锁存的标志 + 夹爪**，不看开关当前值。

→ **"瞬时触发"本身不是失败的充分条件**：成功案例里也存在开关回落。
真正的终局判别始终是**夹爪是否张开**（成功均为 L≈0.98 / R≈0.80，失败均为 R<0.1）。

---

## 6. 判定汇总

| 判定 | 数量 | 案例 |
| --- | ---: | --- |
| `TRANSIENT_EVENT_CONFIRMED` | **2** | kitchen_switch 4300002（完全回退）、smart_home 4300017（差 1° 回退） |
| `PERSISTENT_EVENT_BUT_TERMINAL_FAILURE` | **1** | bakery_close 4300006（开关保持、夹爪闭合） |
| `OTHER_FAILURE` | **3** | room_comfort 4300000/4300004、smart_home 4300011（S2 从未触发；后者第 448 步早停） |
| `SUCCESS_CONTROL` | **2** | kitchen_switch 4300029、bakery_close 4300004 |
| `INCONCLUSIVE` | 0 | — |

---

## 7. 行为不变性证据（是否被动）

对 8 个 episode 逐个与历史 run 同 seed 比对 `s1_step` / `s2_step` / `success`：

| 结果 | 数量 |
| --- | ---: |
| 完全复现（s1、s2、success 全同） | **8/8** |
| 步数也相同 | **7/8** |
| 早停（s1/s2/success 相同但步数 448 vs 1500） | 1（smart_home 4300011，`UnStableError` 中止） |

→ 加入 `articulated` 字段后，轨迹与历史一致，**未见行为扰动**（与 `docs/08` 的三跑 A/B 结论一致）。

---

## 8. 限制（必须一并读）

1. **采样粒度**：每策略步一次；官方 `check_success` 按物理子步调用。1 步内的瞬态会被漏掉。
2. **room_comfort 无 A 类 trace**：目标 seed 4300001 被专家拒，替换为 4300004（见 §2）。
3. **S1 的持续性未量化**：`room_comfort` 的 S1 是"风扇放到垫上（位置+朝向 eps）"，
   我们记录了物体 6D，但**没有目标位姿**，因此没有逐帧判定 S1 是否保持。
4. **开关回退的物理原因未定位**：是弹簧回位、被抓爪带回，还是接触扰动，本 trace 分不出。
5. **不涉及论文**：本文没有、也不能解释论文与本地成功率差距。

---

## 9. 结论

- **事件确实存在"瞬时触发"**：2/8 的失败案例里，子任务标志触发后物理条件不再成立
  （一个完全回退到 0，一个差 1° 回退）。
- **但也存在"持续满足却失败"**：1/8，开关全程保持，失败完全在终局夹爪。
- **更重要的反例**：成功案例里也有开关回落（kitchen_switch 4300029 成功时已低于阈值）。
  因此**不能把"瞬时事件"直接等同于"虚假成功"**——`sr_ordered` 的语义就是"曾经按序触发"，
  而 `env_success` 额外要求夹爪张开。两者的差异主要来自**夹爪终局状态**，不是开关是否保持。
- 这支持 `docs/27` 的判断：这批任务的 `ordered ≫ env` 差异是**指标语义 + 终局夹爪行为**，
  而不是"统计算错"；但**任务代码版本是否与论文一致仍未核实**。

---

## 10. 复现命令

```bash
cd /scratch/lijh/SkillHandoffBench
bash scripts/run_phase4d_trace.sh 1     # room_comfort + kitchen_switch（GPU 2/3）
bash scripts/run_phase4d_trace.sh 2     # smart_home + bakery_close（GPU 3/4）
python scripts/analyze_interaction_trace.py \
  --trace results/phase4d_trace/<task>.jsonl --task <task> \
  --stats <历史 evaluation_statistics.json> --out results/phase4d_trace/<task>_analysis.json
```

原始 trace：`results/phase4d_trace/*.jsonl.gz`（4 个 .gz，共 8.4 MB，可用 `gzip -dc` 还原为原始 JSONL）。
分析结果：`results/phase4d_trace/<task>_analysis.json`。
