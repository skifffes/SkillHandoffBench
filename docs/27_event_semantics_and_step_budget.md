# 27 · 事件语义与步数预算审计（离线，不重跑 VLA）

日期：2026-11-13。数据：`results/paper_table1/full/**`（18 任务 × 2 轨道 × 20 eps）。
脚本：`scripts/analyze_step_budget.py`（只读 `evaluation_statistics.json` 与 `*_subtask_patterns.json`）。
原始输出：`results/paper_table1/step_budget.json`。

> 本文件针对上一轮 `docs/26` 的两个问题做核查：
> ① **"专家筛选解释 60% 差距"是数值敏感性，不是因果结论**——本文件不再使用该措辞；
> ② 差距是否集中在四个 "placement → interaction" 任务，以及这些任务的**完成事件是否真实**。

---

## 1. Q1：步数预算敏感性（不重跑，只用 `s1_step`/`s2_step` 重算）

`ordered@T` = 两个子任务标志按序触发且 `s2_step ≤ T` 的 episode 数。

| 汇总（360 eps/轨道） | @150 | @300 | @500 | @750 | @1000 | @1250 | @1500 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **Oracle 全部 18 任务** | 92 | 136 | 156 | 167 | 169 | 174 | **177** |
| **Full 全部 18 任务** | 24 | 37 | 47 | 60 | 63 | 63 | **68** |
| Oracle · 4 个 interaction | 42 | 46 | 49 | 51 | 51 | 51 | 53 |
| Full · 4 个 interaction | 9 | 15 | 17 | 22 | 24 | 24 | 25 |
| Oracle · 其余 14 任务 | 50 | 90 | 107 | 116 | 118 | 123 | 124 |
| Full · 其余 14 任务 | 15 | 22 | 30 | 38 | 39 | 39 | 43 |

换算成率：

| | @150 | @300 | @500 | @750 | @1000 | @1500 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Oracle | 25.6% | 37.8% | 43.3% | 46.4% | 46.9% | **49.2%** |
| Full | 6.7% | 10.3% | 13.1% | 16.7% | 17.5% | **18.9%** |
| 论文 | 19.7% | 19.7% | 19.7% | 19.7% | 19.7% | **19.7%** |

**读法**：

- **Full Inst**：若论文的最大步数是 **300**，我们是 10.3%，与论文 10.0% 几乎相同；
  1500 步时我们 18.9%，是论文的 1.9 倍。→ **最大步数对 Full 的影响非常大。**
- **Oracle**：即使把预算压到 **150 步**，我们仍是 25.6% > 论文 19.7%。
  → **步数预算单独解释不了 Oracle 的差距**（在 150 步时仍有 92 次 ordered 成功）。
- 四个 interaction 任务的成功来得**很早**（Oracle 在 @150 就有 42/53），
  其余 14 个任务的成功更依赖长预算（@150 只有 50/124）。

**结论（Q1）**：`max_steps` 是 Full Inst 差距的一个有力候选（论文未公开该值），
但对 Oracle 不是主因。这一条**必须在论文核对步数后才能定论**，目前只能记为敏感性。

---

## 2. Q2：四个 interaction 任务的完成事件语义

### 2.1 代码层面（四个任务共用同一套模式）

```python
# 例：room_comfort_2tasks.check_success()
if rot_ok and pos_ok:
    self.subtask_completed[0] = True          # 一旦 True，永不回退
if self.switch.get_qpos()[0] >= limit[1] - 0.05:
    self.subtask_completed[1] = True          # 同上
...
success = all(self.subtask_completed) and gripper_open
```

`kitchen_switch` / `smart_home` / `bakery_close` 的第二子任务都是
**同一个单关节阈值** `switch.get_qpos()[0] >= limit[1] - 0.05`。
→ `sr_ordered` 记录的是"**两个条件曾经按序触发**"，**不保证**触发后物理状态仍成立。

统计口径没错（与官方 `sequential` 字段逐 run 对得上），但**"ordered 成功" ≠ "任务完成"**。

### 2.2 实测拆分（每轨道 20 eps）

| Task | Track | ordered | env 成功 | **两标志按序但终局夹爪闭** | S2 未触发 | S1 未触发 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| bakery_close | oracle | 17 | 7 | **10** | 2 | 1 |
| bakery_close | full | 5 | 0 | **5** | 1 | 14 |
| kitchen_switch | oracle | 11 | **1** | **11** | 4 | 4 |
| kitchen_switch | full | 0 | 0 | 0 | 0 | 20 |
| room_comfort | oracle | 13 | **0** | **13** | 7 | 0 |
| room_comfort | full | 12 | 2 | **10** | 7 | 1 |
| smart_home | oracle | 12 | **0** | **13** | 6 | 1 |
| smart_home | full | 8 | 0 | **10** | 4 | 6 |
| **hobby_desk**（反向对照） | oracle | **0** | **7** | 2 | 6 | 5 |
| hobby_desk | full | **0** | **11** | 1 | 1 | 7 |
| tabletop_arrange（反向对照） | oracle | 3 | 4 | 0 | 7 | 9 |
| tabletop_arrange | full | **0** | **7** | 0 | 0 | 13 |

**三个关键读数：**

1. **`room_comfort` / `kitchen_switch` / `smart_home`（oracle）**：
   两标志按序触发但 env 失败 = **13 / 11 / 13**，而 env 成功只有 **0 / 1 / 0**。
   → 这些"ordered 成功"几乎全部是"**做完两个子任务、但终局夹爪没张开**"。

2. **`hobby_desk` 是反向的极端**：env 成功 **7**（oracle）/ **11**（full），但 ordered **0**。
   → 我们**把任务做成了，但顺序反了**（`s2_step < s1_step`）。
   这解释了论文 35% 而我们 0%：不是做不成，是**反序完成不计分**。

3. **`tabletop_arrange` full**：env 7 而 ordered 0，同样是**反序**。

### 2.3 这四个任务贡献了多少差距（复核上一轮的说法）

| 汇总 | 我们 | 论文（同 18 任务） | 差距（成功次数） | 四个 interaction 贡献 |
| --- | ---: | ---: | ---: | ---: |
| Oracle | 177 | 72（20.0%×360） | **105** | 53 − 7 = **46 → 44%** |
| Full | 68 | 35（9.7%×360） | **33** | 25 − 1 = **24 → 73%** |

→ 与上一轮的判断一致：**四个 interaction 任务贡献 44%（Oracle）/ 73%（Full）的总差距**，
而它们只占 18 个任务里的 22%。**这是当前最值得优先查的地方，而不是"整体偏高"。**

---

## 3. 这些"完成事件"是否真实？（能答与不能答）

| 问题 | 现在能否回答 | 依据 |
| --- | --- | --- |
| 标志是否一经 True 不回退 | ✅ 能 | 代码：`if not self.subtask_completed[i]: ... = True` |
| 终局成功是否还要求夹爪张开 | ✅ 能 | 代码：`success = all(...) and gripper_open`；`gripper_check_mode=full` |
| ordered 成功是否等于任务完成 | ❌ **不能** | 上表：13/11/13 个 episode ordered 成功但 env 失败 |
| 开关关节在触发后**是否仍保持**在阈值以上 | ❌ **不能** | 日志只记 `s2_step` 与终局夹爪，**不记关节 qpos 轨迹** |
| 物体的最终位置/是否稳定 | ❌ **不能** | 未开 trace（`SHB_TRACE_JSONL`），没有逐帧物体位姿 |

**要回答后两行，需要一次带 trace 的重跑**（2 个 episode，约 30 分钟）：
`SHB_TRACE_JSONL` 已实现并做过非干预验证（`docs/08`），逐帧记关节、夹爪、物体 6D、接触数。
但**开关的 qpos 目前不在 trace 字段里**（`_object_poses` 只取 `get_pose()`）——
若要测"开关是否回弹"，需要再加一个只读字段（patch 005，可审计）。

---

## 4. 对 `docs/26` 的更正

| 原文 | 更正 |
| --- | --- |
| "跳过=失败后 oracle 差距从 +29.5 收到 +11~13，**说明专家筛选解释了约 60%**" | 改为：**这只是数值敏感性分析**。官方代码本身也做筛选；若论文同样筛选，则两边都在条件化状态上评测，**不构成实验条件差异**。它**不能**作为因果解释。 |
| 剩余差距"最可能来自 checkpoint / seed / env 版本" | 改为：**证据不足以排序**；但已确认差距**高度集中在四个 interaction 任务**（44% / 73%），且存在**反序完成**（hobby_desk、tabletop_arrange）与**终局夹爪未达标**（room_comfort 等）两种具体机制。 |

---

## 5. 下一步（按性价比排序，均未执行）

| 优先级 | 动作 | 成本 | 能判掉什么 |
| --- | --- | --- | --- |
| 1 | **给四个 interaction 任务各跑 2 个 episode 带 trace**（+ 只读记录 switch qpos） | ~40 min | "事件是瞬时的还是持续的" |
| 2 | **固定 seed、单进程**重跑 1 个任务（对比 5 卡并发时的跳过率） | ~2–3 h | 我的并发是否把筛选搞严了 |
| 3 | **核对论文 max_steps**（若为 300 左右，Full 差距基本消失） | 询问作者 | Q1 的主因 |
| 4 | 向作者索取 checkpoint revision / RoboTwin 版本 / seed 规则 | 询问作者 | 剩余系统性偏差 |

**在这些做完之前，不应把 `docs/26` 的任何一条当作最终科研结论，也不应据此进入 PRTI / DeCo 横评。**
