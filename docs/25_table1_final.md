# 25 · Table 1 最终结果（全量 19 任务）

日期：2026-11-13。协议：`docs/19` / `configs/robocombine_public_protocol_lock.yaml`（锁定的官方公开协议）。
checkpoint：`Motus_robotwin2`（sha256 `70bc1741…300eb65`，与 HF LFS oid 一致，见 `docs/14`/`docs/20`）。
代码：RoboCombine `df237b22bd5c39d705b103daf2b9a8a168c9d453`（服务器运行快照见 `docs/23`）。

> **2026-11-14 计数更正**：上一版写的 "669/760（88%）" 是**错误的**（用了过期的中间态快照 654 再加 15）。
> 逐 pair 审计（`docs/29_count_audit.md`）后的正确口径是：
> **有效完整样本 720 / 760（94.7%）**，即 36 个 pair × 20 eps（全部 20 unique seeds、0 重复、0 中断）；
> `office_organize` **没有任何有效的 20-episode 样本**（仅有 7+7 个部分记录，且续跑目录元数据与明细不一致，已排除）。

**完成度：720 / 760 episodes（94.7%，18/19 任务）**
- 18 个任务 × 2 轨道 = 720 eps 全部跑满 20（已审计）；
- `office_organize_2tasks`：**未完成**，无有效样本（见 §4）。

---

## 1. 最终结果表

`ordered` = 官方 `sr_ordered`（`subtask_completion.sequential.subtask_1_to_2`，与 `summarize_split.py` 复算一致）；
`env` = 官方 `episode_success_rate`。`*` = 未跑满 20。

| Task | Paper Full | Ours Full (ordered) | Ours Full (env) | Paper Oracle | Ours Oracle (ordered) | Ours Oracle (env) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| arrange_sign | 0 | 0/20 (0%) | 0/20 | 10 | 4/20 (20%) | 4/20 |
| bedside | 30 | 12/20 (60%) | 12/20 | 30 | 12/20 (60%) | 12/20 |
| breakfast_prep | 20 | 8/20 (40%) | 8/20 | 75 | 18/20 (90%) | 18/20 |
| checkout_counter | 15 | 6/20 (30%) | 7/20 | 30 | 9/20 (45%) | 7/20 |
| counter_cleanup | 15 | 1/20 (5%) | 5/20 | 15 | 8/20 (40%) | 9/20 |
| desk_arrange | 5 | 2/20 (10%) | 5/20 | 10 | 14/20 (70%) | 14/20 |
| hobby_desk | 15 | **0/20 (0%)** | 11/20 | 35 | **0/20 (0%)** | 7/20 |
| living_room_tidy | 5 | 2/20 (10%) | 2/20 | 10 | 7/20 (35%) | 7/20 |
| office_desk | 10 | 0/20 (0%) | 2/20 | 15 | 9/20 (45%) | 9/20 |
| office_organize | 15 | **未完成**（部分 7 eps，不计入） | — | 15 | **未完成**（部分 7 eps，不计入） | — |
| reception_desk | 5 | 2/20 (10%) | 2/20 | 15 | 11/20 (55%) | 7/20 |
| stationery_sort | 10 | 1/20 (5%) | 3/20 | 10 | 6/20 (30%) | 7/20 |
| store_display | 5 | 2/20 (10%) | 3/20 | 20 | 11/20 (55%) | 11/20 |
| tabletop_arrange | 20 | **0/20 (0%)** | 7/20 | 0 | 3/20 (15%) | 4/20 |
| workspace_setup | 15 | 7/20 (35%) | 5/20 | 50 | 12/20 (60%) | 12/20 |
| bakery_close | 5 | 5/20 (25%) | 0/20 | 35 | 17/20 (85%) | 7/20 |
| kitchen_switch | 0 | 0/20 (0%) | 0/20 | 0 | 11/20 (55%) | 1/20 |
| room_comfort | 0 | 12/20 (60%) | 2/20 | 0 | 13/20 (65%) | 0/20 |
| smart_home | 0 | 8/20 (40%) | 0/20 | 0 | 12/20 (60%) | 0/20 |

---

## 2. 汇总（只用跑满 20 的 18 个任务，共 360 eps/轨道）

| 指标 | Oracle HSE | Full Inst | 论文（19 任务） |
| --- | ---: | ---: | ---: |
| **ordered（论文口径）** | **177/360 = 49.2%** | **68/360 = 18.9%** | 19.7% / 10.0% |
| env success | 136/360 = 37.8% | 74/360 = 20.6% | — |

`office_organize` **不进入任何平均值**：它没有有效样本，剩余 26 个 slot 未跑；
已完成的部分记录（7+7，unique seeds）只作定性参考，且**不能把"未跑的部分"当作失败**。

**注意 `Full Inst` 出现 `env > ordered`**（20.6% vs 18.9%）：因为 `hobby_desk`（env 11、ordered 0）、
`tabletop_arrange`（env 7、ordered 0）、`office_desk`（env 2、ordered 0）存在**反序完成**
——任务做成了，但两个子任务的顺序相反，`sr_ordered` 不计分。

---

## 3. 与论文的差异（结论摘要，详见 `docs/26` / `docs/27` / `docs/28`）

| 结论 | 证据 |
| --- | --- |
| 差距不是均匀的，集中在 4 个 interaction 任务 | 4 任务贡献 Oracle 差距 44%、Full 差距 73%（`docs/27 §2.3`） |
| 存在**反序完成**（我们 env 成功但 ordered 0） | hobby_desk env 7/11 vs ordered 0；tabletop_arrange full env 7 vs ordered 0 |
| 存在**终局夹爪失败**（ordered 成功但 env 0） | room_comfort 13/0、kitchen_switch 11/1、smart_home 12/0 |
| 事件语义含**瞬时触发** | trace 实测：kitchen_switch 4300002 触发后回落到 0（1150 步）、smart_home 4300017 差 1° 回退（1409 步） |
| 也存在**持续满足但终局失败** | bakery_close 4300006 开关全程保持，夹爪始终闭合 |
| 论文未公开的条件仍缺 | `seed` 一词在论文出现 0 次；checkpoint revision、RoboTwin 版本、max steps 均未给 |

**明确不声称**：本文与 `docs/26`–`docs/28` 都**没有**解释论文与本地的成功率差距，只是把差距定位到具体的任务族与事件机制。

---

## 4. `office_organize` 为什么没跑满

- 单 episode 本身只要 ~7 分钟（`avg_episode_time = 407s`），但**专家 demo 极慢且大量失败**：
  7 个接受状态需要 29 个候选，22 次失败 demo 各约 13 分钟 → 5 小时。
- 先后经历：4 次 1h 超时截断 → 2 次 6h 超时 → **原地续跑** → 两次都卡死在专家 demo。
- ⚠️ 原地续跑产生了**记录污染**：`attempt1` 的 `total_episodes=8` 但 `episode_details` 只有 3 条且 seed 重复。
  这是操作失误（应为每次新 `attempt` 目录），已在 `docs/29` 记录并排除该数据。
- 卡死证据（`logs/paper_table1/full/MONITOR_STALLED_20261113.txt`）：

```
oracle  log freeze: 08:55:20, 5079 lines, task.log 2026-11-12 20:02:26, 8 eps
full    log freeze: 09:29:54, 10039 lines, task.log 2026-11-12 23:50:37, 7 eps
both CPU ~110%, GPU util 0%, killed pids 164816 164817
```

判定：`PLANNER_HANG` —— **运行故障标签**（进程长时间无评测进展、CPU 打满、GPU 0%）。
已完成的部分 episode 中 `ordered = 0`、`env = 0`，因此**不影响** §2 的 18 任务汇总；
但"这 15 次全零"**不能推断**剩余 26 次也会失败。

---

## 5. 产物索引

| 内容 | 路径 |
| --- | --- |
| 逐 run 统计 | `results/paper_table1/full/**/evaluation_statistics.json` |
| 分片运行账本 | `results/paper_table1/full/shard*of5/runs.jsonl`、`round3_batch*.out` |
| 卡死留档 | `logs/paper_table1/full/MONITOR_STALLED_20261113.txt` |
| Phase 4D trace | `results/phase4d_trace/*.jsonl.gz` + `*_analysis.json` |
| 协议锁 | `configs/robocombine_public_protocol_lock.yaml`（23 项检查） |
| 差异分析 | `docs/26_discrepancy_analysis.md`、`docs/27_event_semantics_and_step_budget.md`、`docs/28_interaction_event_trace.md` |

---

## 6. 状态码

| 项 | 状态 |
| --- | --- |
| 18 任务 × 2 轨道 × 20 eps | `COMPLETE` |
| `office_organize` × 2 轨道 | `PLANNER_HANG`（**无有效样本**；部分 7+7，记录不一致已排除） |
| 公开代码协议 | `REPRODUCED_AT_PUBLIC_CODE_LEVEL` |
| 论文精确复现 | `NOT_CLAIMED`（checkpoint revision / seed 规则 / RoboTwin 版本未公开） |
| `ordered_hse` 轨道 | `NOT_RUN`（缺 predictor bundle） |
