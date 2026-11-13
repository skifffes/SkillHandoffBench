# 26 · 差距分析：为什么我们的数字比论文高（以及高多少）

日期：2026-11-13。范围：公开 RoboCombine 协议 + 公开 Motus checkpoint 的复现结果，
**18 个任务 × 2 轨道 × 20 episodes = 720 次 rollout**（`office_organize` 两轨道各 7/20 未满，已排除，见 §7）。

> 本文件回答一个问题：**"我们 oracle 49%、论文 20%，差在哪？"**
> 结论先说：**其中约 60% 的 oracle 差距、以及几乎全部 full_inst 差距，可以用"专家筛选只留好状态"解释完**；
> 剩下的差距不是均匀的，而是集中在少数任务、且**双向**（有的我们高、有的我们低）。

---

## 1. 三种口径（必须先分清）

| 口径 | 定义 | 分母 | 性质 |
| --- | --- | ---: | --- |
| **A. 正式结果（filtered）** | 官方代码跑出来的 20 个 expert-valid 初始状态 | 360 | **实测** |
| **B. 跳过=失败（unfiltered）** | 把专家跳过的候选 seed 全部当失败 | 573 / 569 | **反事实估计** |
| **C. 前 20 个原始 seed** | 只数 `4300000–4300019` 里的成功，其余当失败 | 360 | **反事实估计**（最接近"不做筛选、直接跑 20 次"） |

B/C 都是**假设**，不是实测——被跳过的 seed 我们从未评测过。它们的作用是**量化"筛选"这个机制的贡献**，
**不能**写进结果表当成绩。

---

## 2. 主表（18 任务逐项）

| Task | Track | 论文 | A 正式(20) | B 跳过=失败(全候选) | C 前20原始seed |
| --- | --- | ---: | ---: | ---: | ---: |
| arrange_sign | oracle | 10% | 20% | 11% | 10% (2/20) |
| arrange_sign | full | 0 | 0% | 0% | 0% (0/20) |
| bedside | oracle | 30% | 60% | 29% | **30% (6/20)** |
| bedside | full | 30% | 60% | 29% | 25% (5/20) |
| breakfast_prep | oracle | 75% | 90% | 78% | **80% (16/20)** |
| breakfast_prep | full | 20% | 40% | 35% | 40% (8/20) |
| checkout_counter | oracle | 30% | 45% | 30% | 20% (4/20) |
| checkout_counter | full | 15% | 30% | 19% | **15% (3/20)** |
| counter_cleanup | oracle | 15% | 40% | 30% | 25% (5/20) |
| counter_cleanup | full | 15% | 5% | 4% | 5% (1/20) |
| desk_arrange | oracle | 10% | **70%** | 56% | **60% (12/20)** |
| desk_arrange | full | 5% | 10% | 9% | 10% (2/20) |
| hobby_desk | oracle | 35% | **0%** | 0% | **0% (0/20)** |
| hobby_desk | full | 15% | **0%** | 0% | **0% (0/20)** |
| living_room_tidy | oracle | 10% | 35% | 32% | 30% (6/20) |
| living_room_tidy | full | 5% | 10% | 10% | **10% (2/20)** |
| office_desk | oracle | 15% | 45% | 26% | 35% (7/20) |
| office_desk | full | 10% | 0% | 0% | 0% (0/20) |
| reception_desk | oracle | 15% | 55% | 52% | **50% (10/20)** |
| reception_desk | full | 5% | 10% | 10% | **10% (2/20)** |
| stationery_sort | oracle | 10% | 30% | 15% | **15% (3/20)** |
| stationery_sort | full | 10% | 5% | 2% | 5% (1/20) |
| store_display | oracle | 20% | 55% | 48% | 45% (9/20) |
| store_display | full | 5% | 10% | 8% | **10% (2/20)** |
| tabletop_arrange | oracle | 0 | 15% | 11% | 10% (2/20) |
| tabletop_arrange | full | 20% | **0%** | 0% | **0% (0/20)** |
| workspace_setup | oracle | 50% | 60% | 55% | **55% (11/20)** |
| workspace_setup | full | 15% | 35% | 32% | 35% (7/20) |
| bakery_close | oracle | 35% | 85% | 53% | 55% (11/20) |
| bakery_close | full | 5% | 25% | 16% | 10% (2/20) |
| kitchen_switch | oracle | 0 | 55% | 28% | 25% (5/20) |
| kitchen_switch | full | 0 | 0% | 0% | 0% (0/20) |
| room_comfort | oracle | 0 | 65% | 39% | 25% (5/20) |
| room_comfort | full | 0 | 60% | 41% | 35% (7/20) |
| smart_home | oracle | 0 | 60% | 21% | 15% (3/20) |
| smart_home | full | 0 | 40% | 14% | 10% (2/20) |

（加粗 = 与论文差距 ≤5pp）

---

## 3. 汇总

| 口径 | Oracle HSE | Full Inst |
| --- | ---: | ---: |
| **论文**（19 任务） | **19.7%** | **10.0%** |
| 论文（同 18 任务均值） | 20.0% | 9.7% |
| **A 正式（filtered）** | **49.2%**（177/360）CI [44.0, 54.3] | **18.9%**（68/360）CI [15.2, 23.3] |
| **B 跳过=失败（全候选）** | **30.9%**（177/573）CI [27.2, 34.8] | **12.0%**（68/569）CI [9.5, 14.9] |
| **C 前 20 原始 seed** | **32.5%**（117/360）CI [27.9, 37.5] | **12.2%**（44/360）CI [9.2, 16.0] |

**读法**：

- `full_inst`：18.9% → **12.0–12.2%**，论文 10.0%，**差距 2.0–2.2pp，落在 CI 内**。
- `oracle_hse`：49.2% → **30.9–32.5%**，论文 19.7%，**差距从 +29.5pp 收到 +11~13pp**（2.5 倍 → 1.6 倍）。

---

## 4. 因素一：专家筛选（解释力最强，且可量化）

### 4.1 机制

官方 `script/eval_policy.py:775-790`：对每个候选 seed 先让**脚本专家**跑一遍

```
task_env.setup_demo(seed) → task_env.play_once() → close_env()
if not (task_env.plan_success and task_env.check_success()):
    continue          # 该 seed 被丢弃，不计数
```

专家的实现：任务 env 里的 `play_once()`（作者手写轨迹）+ **CuRobo** 规划器
（`assets/embodiments/aloha-agilex/config.yml: planner: "curobo"`），
失败判据见 `envs/_base_task.py:886/896/905/915/924/945/948`（目标位姿为 None / 规划 `status != 'Success'` / 双臂异常）。

### 4.2 我们实际筛掉了多少（首次公开量化）

| 轨道 | 候选 seed 数 | 接受 | **跳过** | 跳过率 |
| --- | ---: | ---: | ---: | ---: |
| oracle_hse（18 任务） | **573** | 360 | **213** | **37%** |
| full_inst（18 任务） | **569** | 360 | **209** | **37%** |

单任务差异极大：

| 任务 | 候选 | 跳过 | 任务 | 候选 | 跳过 |
| --- | ---: | ---: | --- | ---: | ---: |
| smart_home | 58 | **38** | breakfast_prep | 23 | 3 |
| kitchen_switch | 40–43 | 20–23 | desk_arrange | 23–25 | 3–5 |
| stationery_sort | 41–43 | 21–23 | living_room_tidy | 20–22 | **0–2** |

### 4.3 为什么这会抬高成功率

被跳过的状态是**专家都做不成**的状态——通常是物体位置刁钻、够不到、容易碰倒。
这些恰好也是 VLA 最容易失败的场景。把它们剔除，等于**只考容易题**。
跳过率越高的任务，我们相对论文高得越多，这一点与数据吻合（smart_home 跳 38 → 我们 +60pp；
living_room 跳 0–2 → 我们 +25pp；breakfast 跳 3 → +15pp）。

### 4.4 一个必须承认的副作用：筛选本身不稳定

同一任务、同一 seed、同一配置，两条轨道的专家跳过数不同：

| 任务 | oracle 跳过 | full 跳过 |
| --- | ---: | ---: |
| kitchen_switch | 18 | **21** |
| stationery_sort | 20 | **22** |

→ CuRobo 规划带随机性、且对 CPU 负载敏感（我们 5 卡并发）。这意味着：
**① "20 个初始状态"不可复现；② 两条轨道不是配对样本。**

---

## 5. 因素二：checkpoint（可能，但无法核对）

| 项 | 状态 |
| --- | --- |
| 本地权重 | `Motus_robotwin2`，sha256 `70bc1741…300eb65` |
| HF 公开文件 | `motus-robotics/Motus_robotwin2`（repo sha `ab74bc214f7f…`），LFS oid **与本地一致** |
| 论文所用 revision | **未公开** → `PAPER_CHECKPOINT_REVISION_UNVERIFIED` |

即：**"公开文件一致"已证，但"论文用的是这份"无法证**。

---

## 6. 因素三：任务/环境版本（能解释"反向"任务）

不是所有任务都偏高，**有三个是反向的**：

| Task | Track | 论文 | 我们(C) | 差 |
| --- | --- | ---: | ---: | ---: |
| hobby_desk | oracle | 35% | 0% | **−35** |
| hobby_desk | full | 15% | 0% | **−15** |
| tabletop_arrange | full | 20% | 0% | **−20** |
| counter_cleanup | full | 15% | 5% | −10 |

"我们的模型全面更强"解释不了这些。更可能是**任务/env 版本差异**（物体尺寸、摩擦、判定阈值）
或该任务的专家在我们环境下行为不同。论文只说 "built on RoboTwin [5]"，**未给版本号**。

---

## 7. 因素四：指标口径（已核对，不是误差来源）

官方定义（`handoff_eval/summary/summarize_split.py`）：
`sr_ordered = subtask_completion.sequential["subtask_1_to_2"].rate`，
判定条件是 **`s1_step ≤ s2_step` 且两个子任务都完成**，**不包含终局夹爪条件**。

我们把每个 run 的重算值与官方字段逐一对过（例：`room_comfort` 重算 13/20 = 0.65，官方 `count=13, rate=0.65`）。
所以**口径没算错**，但要注意它测的是"子任务按序满足"，不是"任务成功"：

| 任务 | ordered | env success |
| --- | ---: | ---: |
| room_comfort | 13/20 | **0** |
| kitchen_switch | 11/20 | **1** |
| smart_home | 12/20 | **0** |

这些 episode 两件事都做对了、但最后夹爪状态不达标。论文在这三个任务报 0%，
说明他们的模型连子任务条件都没满足过——是行为差异，不是指标差异。

---

## 8. 为什么不能写"复现成功"

1. **19 任务没跑完**：`office_organize` 两轨道各 7/20（单 episode 极慢 + 专家 demo 反复失败，
   已在原地续跑）。任何"19 任务总体"的数字目前都不成立。
2. **B/C 是反事实估计**，不是实测；写进成绩表就是造假。
3. **专家筛选不可复现**（§4.4），意味着连我们自己重跑同一任务都得不到同一批 20 个状态。

---

## 9. 要把差距彻底定死，需要四个实验（都未执行）

| # | 实验 | 能判掉什么 | 成本 |
| --- | --- | --- | --- |
| E1 | **无筛选对照**：固定 seed 列表直接评测（跳过专家检查），与筛选后对比 | 因素一（量化到 pp） | ~2 任务 × 20 eps ≈ 4h |
| E2 | **checkpoint 替换**：拿到论文权重或其 sha256 | 因素二（唯一能彻底排除的） | 取决于能否拿到 |
| E3 | **env 版本对齐**：比对 RoboTwin 版本与资产哈希，重点查 hobby_desk / tabletop_arrange | 因素三 | 1–2 天（需作者资料） |
| E4 | **base seed 扫描**：43/44/45 各跑 20 次 | 减少 seed 分布的系统风险 | 3 × 20 × 2 ≈ 8h |

E1 是唯一"现在就能做、且能给出确定结论"的。但它**改变了官方协议**，只能作为对照实验单独标注，
不能回灌进正式表。

---

## 10. 证据索引

| 内容 | 位置 |
| --- | --- |
| 专家筛选逻辑 | `script/eval_policy.py:775-790`（跳过不计数）；`:134-152`（seed 缓存读写） |
| 专家失败判据 | `envs/_base_task.py:886/896/905/915/924/945/948` |
| 规划器选择 | `assets/embodiments/aloha-agilex/config.yml:22` → `planner: "curobo"` |
| `sr_ordered` 定义 | `handoff_eval/summary/summarize_split.py`；`eval_policy.py:576-593` |
| chunk-preserving | `handoff_eval/hse.py:177-184`（缓存空才切）；`policy/Motus/deploy_policy.py:68-75` |
| 官方仓库 | `df237b22bd5c39d705b103daf2b9a8a168c9d453`（2026-10-15，至今未变） |
| 服务器运行目录 | 同 HEAD；3 个文件有 patch（`docs/23_server_runtime_snapshot.md`，逐文件 sha256） |
| 论文关键词统计 | `seed` 0 次、`filter` 0 次、`expert` 5 次（全在参考文献）、`rollout` 12 次 |
| 仓库是否发布 seed receipt | **否**（`git ls-files | grep seed` 为空；`docs/` 只有 `runtime_envs.md`） |
| 原始统计 | `results/paper_table1/full/**/evaluation_statistics.json` |

---

## 11. 一句话结论

**公开代码层面：可复现（full_inst 按"跳过=失败"口径 12.2% vs 论文 10.0%，已落在置信区间内）。
论文精确复现：不能声称（checkpoint revision、seed 生成方式、env 版本三项未公开）。
剩余 oracle 差距（32.5% vs 19.7%）集中在 desk_arrange / room_comfort / kitchen_switch / smart_home 等少数任务，
且存在反向案例（hobby_desk 0% vs 35%），因此不能用单一因素解释，也不能靠调参去"凑近"。**
