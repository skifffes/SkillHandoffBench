# 07 · 多任务交接瓶颈筛查（Gate C）

运行时间：2026-11-07 12:28–14:27 CST。**15 次真实 rollout**（5 任务 × 3 episode），
`Motus + oracle_hse`，单卡 A40，冻结权重。

---

## 1. 任务集（执行前固定，不按成功率挑选）

| # | 任务 | 第一阶段 | 第二阶段（下游技能） | 覆盖的技能类型 |
| --- | --- | --- | --- | --- |
| 1 | `arrange_sign_2tasks` | Sort objects | **Rotate QR code** | 旋转/对准 |
| 2 | `breakfast_prep_2tasks` | Place cup on coaster | **Place bread in basket** | 放进容器 |
| 3 | `desk_arrange_2tasks` | Move stapler to pad | **Place phone on stand** | 薄物体 + 立式支撑 |
| 4 | `office_organize_2tasks` | Place mouse on pad | **Stamp seal** | 垂直按压 |
| 5 | `bakery_close_2tasks` | Place bread in basket | **Turn switch** | 小物件精细操作 |

依据是任务书给定的"覆盖不同下游技能与接触需求"；**没有**按成功率筛选，跑完后也没有换任务。

---

## 2. 受控条件与 seed 实况

| 项 | 取值 |
| --- | --- |
| checkpoint | `Motus_robotwin2`，sha256 `70bc1741…` |
| track / policy | `oracle_hse` / `Motus` |
| 判据 | 官方 `check_success()`，未改 |
| 步数上限 | 1500 |
| `--clear-cache` | `false` |
| 计划 seed | 每任务 `4300000, 4300001, 4300002` |
| **实际 seed** | 见下表（**有任务因为专家 demo 失败而顺延到后面的 seed**） |

**实际使用的 seed（来自 `evaluation_statistics.json`，不是计划值）**

| 任务 | 实际 seed | 偏差原因 |
| --- | --- | --- |
| arrange_sign | `4300004, 4300007, 4300008` | 4300000/1/2/3/5/6 的**专家 demo 报错**：`target_pose cannot be None for move action` |
| breakfast_prep | `4300000, 4300001, 4300002` | 无 |
| desk_arrange | `4300001, 4300002, 4300003` | 4300000 专家 demo 失败 |
| office_organize | `4300000, 4300002, 4300014` | 4300001、4300003–4300013 专家 demo 失败（顺延 14 个） |
| bakery_close | `4300001, 4300004, 4300006` | 4300000、4300002、4300003 专家 demo 失败 |

> 这是**官方评测循环**的行为（`eval_policy.py:780-789`：专家 demo 失败就 `continue`），
> 不是我们挑 seed。但它有两个后果必须写清楚：
> 1. "3 个独立初始状态"实际是**经专家可行性过滤后**的 3 个；
> 2. 不同任务的 seed 集合不同，**任务间不能按 seed 配对比较**。

---

## 3. 结果总表（每个比例都是 分子/分母）

| Task | Stage 1 | Stage 2 | Ordered Success | Transition Conversion (s2/s1) | Switch events | 首次失败位置 | 步数 mean/max | Candidate? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `arrange_sign_2tasks` | **2/3** | 2/3 | **0/3** | 2/2 | 2 | stage1×1, post_success×2 | 1500/1500 | 边界（见 §5） |
| `bakery_close_2tasks` | 3/3 | 3/3 | **2/3** | 3/3 | 3 | post_success×1 | 629/1500 | 边界 |
| `breakfast_prep_2tasks` | 3/3 | 3/3 | **3/3** | 3/3 | 3 | — | 160/196 | 观察项 |
| `desk_arrange_2tasks` | 3/3 | **2/3** | **2/3** | **2/3** | 3 | **stage2×1** | 1006/1500 | **是** |
| `office_organize_2tasks` | 3/3 | **2/3** | **2/3** | **2/3** | 3 | **stage2×1** | 808/1500 | **是** |
| **合计** | **14/15** | **12/15** | **9/15** | **12/14** | 14 | — | — | — |

> `Transition Conversion` 按任务书定义 = 第二阶段成功 / 第一阶段成功。
> 另有口径 `downstream_success_among_switched`（已切换 episode 中第二阶段成功的比例），
> 本次两者数值相同（因为每个第一阶段成功的 episode 都发生了切换）。

### 3.1 逐 episode（原始数据）

| Task | seed | 成功 | 总步数 | S1 步 | S2 步 | cue→switch | 切换事件 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| arrange_sign | 4300004 | ❌ | 1500 | — | — | — | **0** |
| arrange_sign | 4300007 | ❌ | 1500 | 811 | 1259 | 5 | 1 |
| arrange_sign | 4300008 | ❌ | 1500 | 343 | 80 | 9 | 1 |
| bakery_close | 4300001 | ✅ | 248 | 37 | 112 | 11 | 1 |
| bakery_close | 4300004 | ✅ | 140 | 41 | 64 | 7 | 1 |
| bakery_close | 4300006 | ❌ | 1500 | 38 | 218 | 10 | 1 |
| breakfast_prep | 4300000 | ✅ | 143 | 51 | 104 | 13 | 1 |
| breakfast_prep | 4300001 | ✅ | 196 | 51 | 112 | 13 | 1 |
| breakfast_prep | 4300002 | ✅ | 142 | 51 | 109 | 13 | 1 |
| desk_arrange | 4300001 | ✅ | 752 | 51 | 706 | 13 | 1 |
| desk_arrange | 4300002 | ✅ | 767 | 399 | 478 | 1 | 1 |
| desk_arrange | 4300003 | ❌ | 1500 | 42 | — | 6 | 1 |
| office_organize | 4300000 | ❌ | 1500 | 41 | — | 7 | 1 |
| office_organize | 4300002 | ✅ | 477 | 43 | 447 | 5 | 1 |
| office_organize | 4300014 | ✅ | 448 | 137 | 347 | 7 | 1 |

产物：`results/phase2/_summary/gateC/{tasks.csv,episodes.csv,summary.json,table.md}`；
原始：`results/phase2/gateC_<task>/robocombine/oracle_hse/Motus/<run_id>/tasks/<task>/`。

---

## 4. 三种失败形态（必须分开，否则会误判）

| 形态 | 判定 | 本次出现的 episode |
| --- | --- | --- |
| **A. 阶段 1 从未完成** | 原子能力/指令跟随问题，**不能归因于交接** | arrange_sign 4300004（1500 步 S1 始终 False） |
| **B. 阶段 1 完成、切换发生，阶段 2 从未完成** | **潜在交接问题**（仍需 Gate D 确认原因） | desk_arrange 4300003（S1@42，之后 1458 步无 S2）、office_organize 4300000（S1@41，之后 1459 步无 S2） |
| **C. 两个子任务都完成，但终局"夹爪张开"没满足** | **不是交接问题**，是终局判据/行为问题 | arrange_sign 4300007、4300008；bakery_close 4300006 |

**形态 C 是本轮最容易被误读的地方**：如果只看 `ordered success`，
arrange_sign 是 0/3、bakery_close 是 2/3；但按"子任务完成度"看，arrange_sign 其实是 **2/3 双阶段都完成**。
这两类不能混成一个"交接失败率"。

另外，`failure_analysis.by_type` 会把这些**归类成 `timeout`**（因为 episode 跑满 1500 步），
所以**不能直接用官方 `failure_analysis` 判断失败类型**，必须结合 `s1_completed/s2_completed`
以及 `all_subtasks_but_not_success`（`scripts/collect_phase2.py` 输出的字段）。

---

## 5. 候选任务评估（写死规则，见下）

规则（在跑之前就已写进 `scripts/collect_phase2.py`）：
1. 阶段 1 = 0 → **否**（原子能力瓶颈）；
2. 有 `stage2` 失败且 ordered 未满 → **是**（阶段 1 成功但下游失败）；
3. 只有"子任务全成但终局夹爪未达标" → **边界**（非交接）；
4. 全成功 → **观察项**。

| 任务 | 判定 | 理由 |
| --- | --- | --- |
| `desk_arrange_2tasks` | **强候选** | 3/3 阶段 1 成功（51/399/42 步），1 次纯下游失败（S1@42 后 1458 步无 S2），另外两次成功但很慢（752/767 步） |
| `office_organize_2tasks` | **强候选** | 3/3 阶段 1 成功（41/43/137 步），1 次纯下游失败（S1@41 后 1459 步无 S2） |
| `bakery_close_2tasks` | 边界 | 下游其实全成（3/3），失败是终局夹爪；适合做"终局判据"研究，不适合做交接研究 |
| `arrange_sign_2tasks` | 边界/不可用 | 1/3 阶段 1 从未完成 + 2/3 子任务全成但夹爪不达标；且 6/9 个 seed 专家 demo 失败 → 初始状态可用性差 |
| `breakfast_prep_2tasks` | 观察项 | 3/3 全成功、步骤极短（142–196），没有失败样本可供分析 |

---

## 6. 结论

1. **找到了"阶段 1 成功、切换发生、阶段 2 失败"的案例**：`desk_arrange` seed 4300003 与
   `office_organize` seed 4300000 —— 都是第一阶段 41–42 步完成，之后 1400+ 步第二阶段毫无进展。
2. 但同时出现的还有两类**非交接**失败（A 与 C），若合并统计会显著高估"交接失败率"。
3. 任务难度差异很大：`breakfast_prep` 3/3 且 ≤196 步；`arrange_sign` 0/3 且 6/9 个 seed
   连专家都做不成。**任务间不能直接平均**。
4. 因此下一轮正式实验只应取 `desk_arrange` + `office_organize`（必要时加 `bakery_close` 做终局判据对照），
   并且**必须用未参与本轮筛查的新 seed**（例如 `base-seed 43` → `4400000` 起）。

> **退出码说明**：本文件所有数字都取自 `evaluation_statistics.json`。所有 Phase 2 子进程都以 `code=-11`（SIGSEGV）结束，但那是 **main() 返回之后**的解释器析构崩溃（`_result.txt` 已写出、stats 完整），不影响指标，详见 `docs/08 §6`。

