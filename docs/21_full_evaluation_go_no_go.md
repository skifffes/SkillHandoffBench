# 21 · 全量复现决策（Gate F）

日期：2026-11-10。依据：`docs/19`（协议对照）、`docs/20`（数据勘误）、
`configs/robocombine_public_protocol_lock.yaml`（锁定快照 + `scripts/check_protocol_lock.py` 23 项全 PASS）。

---

## F1. `PUBLIC_CODE_REPRODUCIBLE` = **YES**

| 判据 | 证据 |
| --- | --- |
| 官方仓库未变，本地即 HEAD | GitHub API sha `df237b2…` == 本地 `git rev-parse HEAD` |
| 协议参数可锁定并自动校验 | `check_protocol_lock.py` 23/23 PASS（spec hash、scene yml hash、README 声明、runner 默认值、专家筛选锚点、`hse.flush_pending_switch`、全部 `command.sh` 的 `--episode_num 20` 与 `--clear_cache false`） |
| 已完成 4 组 N=20 且跑满 | living/office × oracle/full 各 20 completed，`episode_details` 条数 = 20 |
| 指标可复算 | `sr_ordered` 由 `s1_step ≤ s2_step` 重算，与 `summarize_split` 语义一致；`env success` 单列 |
| 崩溃可区分 | `-11`（评测后 SIGSEGV）不影响 stats；`124`（外层 timeout）会截断，必须按 completed 计数 |

**已知瑕疵（不否定 F1，但必须写进每个报告）**：
① N>3 时两条轨道的 accepted seed 集合不同（`MISMATCH`，见 `docs/20 §2`）；
② 复用 `save_dir` 会让 `total_successes` 与 `episode_details` 不自洽（`docs/20 §4`）。

---

## F2. `PAPER_EXACT_REPRODUCIBLE` = **NO**

| 缺什么 | 影响 | 是否可从公开信息补齐 |
| --- | --- | --- |
| 论文 Table 1 的 **base seed / accepted seed receipts** | 成功率会因初始状态分布而差 2–4 倍 | ❌ 论文与仓库都未发布 |
| 论文所用 **Motus checkpoint revision** | 公开权重已逐字节核验（`PUBLIC_CHECKPOINT_PARITY_VERIFIED`），但论文没声明"用的就是它" | ❌ 需作者确认 |
| **max steps / RoboTwin 版本 / 训练数据** 的论文口径 | 影响长尾失败率 | ❌ 论文未写 |

→ 结论：**可以复现"官方公开代码协议的实验结果"，但不能声称"精确复现论文 Table 1"。**
   这一限制来自信息缺失，不是我们的实现问题。

---

## F3. `FULL_EVAL_GO / HOLD / BLOCKED` = **GO（限 PROTOCOL O）**

**GO 的理由**：
- 配置已锁定并自动校验；关键语义（chunk-preserving、专家筛选、`sr_ordered`）都有源码锚点+本地实测；
- 资源可用（A40 ×5，当前空闲），已完成 4 组 N=20 证明管线稳定；
- 已知问题（配对、续跑、超时）**都有明确的操作规范可规避**，不构成阻塞。

**但必须按以下规范执行**（否则会出现 HOLD 级问题）：

| 风险 | 规范 |
| --- | --- |
| 55 min 外层 `timeout` 截断（本轮就是它把 probe 砍断） | 每次 invocation **只跑 1 个 task × 1 个 track × 20 eps**，`timeout 21600`（6h）；**不要**用 12h 一次跑 3 个任务 |
| 截断后误计数 | 统计只认 `episode_details`；`completed < 20` 的 run 标 `INCOMPLETE`，**不进** 19 任务汇总 |
| 续跑改变样本总体 | **每个 batch 用全新 `output-root`**；绝不向已有 `save_dir` 追加；如需补跑，另起目录并两段分开报告 |
| `total_successes` 不可信 | 一律从 `episode_details` 重算 env/ordered，`check_paper_reproduction.py` 已如此实现 |
| 崩溃码混淆 | 保存 `exit`；`-11` 视为完成、`124` 视为截断，两者都原样记录 |
| 轨道不配对 | 报告里**逐任务**给两轨道各自的 seed 列表；不做"配对差值"的推断（除非另开 `CONTROLLED_PAIRED_PROTOCOL`，见 §3） |

---

## 1. 任务级进度（19 个任务）

| 状态 | 任务 | 说明 |
| --- | --- | --- |
| ✅ 已完成 N=20 × 2 轨道 | `living_room_tidy_2tasks`、`office_desk_2tasks` | 80 rollouts，见 `docs/15` |
| ⚠️ 只有 probe（N=5，base 45，不计入 760） | `breakfast_prep_2tasks`、`workspace_setup_2tasks`、`bakery_close_2tasks` | 需用 base 42 重跑 N=20 |
| ⬜ 未运行 | `arrange_sign`、`bedside`、`checkout_counter`、`counter_cleanup`、`desk_arrange`、`hobby_desk`、`office_organize`、`reception_desk`、`stationery_sort`、`store_display`、`tabletop_arrange`、`kitchen_switch`、`room_comfort`、`smart_home` | 14 个 |

**剩余需要：17 个任务 × 2 轨道 × 20 eps = 680 个完整 rollout**（probe 的 14 个不能抵）。

---

## 2. 运行方案

2.1 **批次划分**：按任务切 17 个批次，每批次 2 个 invocation（oracle / full），每个 invocation 20 eps。

2.2 **时间估算（用实测速度）**：
- 深跑实测：oracle 40 eps ≈ 5.2 h（7.8 min/ep）；full 40 eps ≈ 7.1 h（10.7 min/ep）。
- 680 eps 单卡 ≈ **100–110 小时（约 4.5 天）**。
- 5 张 A40 并行（每卡 1 进程，41 GB 显存，余量够）→ **约 24–30 小时**。
- 磁盘：每组产物 ~1–3 MB 统计 + 可选图像；trace 若开启则 GB 级（**全量评测不开 trace**）。

2.3 **命令模板**（与已完成的 4 组逐字一致，只换 `--task-filter` 与 output）：

```bash
bash scripts/run_paper_reproduction.sh full oracle_hse b1 1   # 一次 1 个任务
# 内部：run_split --episodes 20 --max-steps-per-episode 1500 --clear-cache false --base-seed 42
```

2.4 **逐批验收**（每批跑完立即执行，不通过就暂停而不是继续堆数据）：

```bash
python scripts/check_paper_reproduction.py --root results/paper_table1/gateE/<batch> \
    --track oracle_hse --expected-episodes 20 --json .../check.json
```
要求：`episodes == 20` 且 `problems` 为空，否则该批标 `INCOMPLETE` 并单独重跑。

---

## 3. 若要做"配对"研究：必须另立协议

- 名称：**`CONTROLLED_PAIRED_PROTOCOL`**（不得叫论文协议）。
- 实现：绕过 `run_split`，直调 `eval_policy.py --priority_seeds_file <固定 seed 列表>`
  （`run_split` 不支持该参数，实测 `exit=2`）。
- 目录：`results/paper_controlled_paired/`，与 `results/paper_table1/` **物理隔离**。
- 前置：先用 `setup_demo` 对候选 seed 做一次"专家可行性预筛"，把可行 seed 固定下来，
  再让两条轨道**用同一份列表**跑——但必须记录"预筛本身也是对官方分布的一次改变"。
- 报告：`pairwise Δ` 只能在这一协议下说，不能回灌到 Table 1。

---

## 4. 与论文差异的标注方式（不做"逼近"）

1. 每个任务给 **paper / ours(oracle) / ours(full)** 三列 + `diff`，**不做**汇总时剔除异常任务。
2. 汇总同时给：逐任务均值（论文口径 19 任务等权）、以及"已完成任务子集"的均值（并注明子集）。
3. 给 Wilson 95% CI；n=20 时 ±约 18 pp，n=40 时 ±约 12 pp。
4. 已知系统性偏差（oracle 偏高 25–50 pp、full 偏低 0–20 pp）**照实写**，
   归因候选：checkpoint 不同（公开一致 ≠ 论文所用）、seed 分布不同、专家筛选差异。
5. **禁止**：换 seed、关筛选、改判据、挑任务来让数字接近论文。

---

## 5. 最小必要动作（下一步，不含全量）

1. ~~锁定配置~~ ✅（`configs/robocombine_public_protocol_lock.yaml` + checker + 3 个 CPU 测试）
2. 决定是否批准 680 rollouts（单卡 4.5 天 / 5 卡 1 天）。
3. 若批准：先跑 **1 个新任务**（建议 `breakfast_prep_2tasks`，论文 oracle 75%、我们 probe 100%，判别力最强）
   作为流程演练，验收通过后再批量。
4. 若暂不批准：现有 4 组 N=20 已足以支撑"公开代码可复现 + 与论文存在系统性偏差"这一结论。

---

## 6. 一句话结论

**公开代码层面：GO。论文精确复现：NO（信息缺失）。**
现在缺的不是算力或代码，而是**论文原始 seed receipts 与 checkpoint revision**；
在拿到之前，任何"接近 19.7%"的目标都不应该成为实验设计依据。
