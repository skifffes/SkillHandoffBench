# 24 · 演练验收（Breakfast Prep × 2 轨道 × N=20）

日期：2026-11-11。演练按 `docs/21`/`docs/23` 的执行前规范启动，**40 次正式 rollout**（非 probe）。

---

## 1. 结果

| Task | Track | requested | **completed** | env success | **sr_ordered** | ours % | paper % | diff |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| breakfast_prep_2tasks | oracle_hse | 20 | **20** | 18/20 | **18/20** | **90.0** | 75.0 | **+15.0** |
| breakfast_prep_2tasks | full_inst | 20 | **20** | 8/20 | **8/20** | **40.0** | 20.0 | **+20.0** |

- 两轨道的 `ordered == env`：**没有出现乱序完成**，所以这次 `sr_ordered` 与环境成功同值。
- 实际 seeds（两轨道**完全相同**）：
  `4300000–4300006, 4300008–4300010, 4300012–4300020, 4300022`
  （候选 4300000–4300022 共 23 个，被专家跳过 3 个：**4300007、4300011、4300021**）
- 本次是**天然配对**：两条轨道接受了同一批 20 个初始状态，因此 90% vs 40% 的差可以直接归因于
  指令/切换方式（这是本轮唯一一次真正配对的 N=20 对比）。

产物：
`results/paper_table1/full/{oracle_hse,full_inst}/breakfast_prep_2tasks/attempt1/`
日志：`logs/paper_table1/full/{oracle_hse,full_inst}__breakfast_prep_2tasks__a1.log`
机器检查：`results/paper_table1/full/check_{oracle_hse,full_inst}.json`

---

## 2. 验收清单（逐条对照批准条件）

| # | 条件 | 结果 |
| --- | --- | --- |
| 1 | 每轨道 20 条**完整** episode | ✅ `episode_details` 各 20 条（checker：`eps=20`，`problems=-`） |
| 2 | 按原始记录重算 `sr_ordered` | ✅ 18/20、8/20，由 `s1_step ≤ s2_step` 重算，未用 `metadata` |
| 3 | 保留异常退出码 | ✅ 子进程 `code=-11`（评测后 SIGSEGV，`stats=yes`）原样记录；supervisor 记 `exit=1` 但 `completed=20`，**未当成失败** |
| 4 | `124` 不代表此前完整 episode 无效 | ✅ 本次无 124；即便有，统计只数 `episode_details`，已完成的不会被丢 |
| 5 | 独立输出目录 | ✅ 每 (track,task) 独立 `attempt1`；probe（base 45）在 `probe/`，**未混用** |
| 6 | 未调 seed / 未挑 seed | ✅ seed 严格按 `range(4300000…)` 递增，仅跳过专家未通过的 3 个 |
| 7 | 运行源码未被动过 | ✅ 三个 patch 文件 sha256 与 `docs/23` 快照一致（`6493ca49…`/`72b042f9…`/`192f5204…`），HEAD 仍 `df237b2` |

---

## 3. 耗时（用于排期）

| 轨道 | 开始 | 结束 | 20 eps 用时 |
| --- | --- | --- | ---: |
| oracle_hse | 12:35:53 | 13:34:17 | **58 分钟**（2.9 min/ep） |
| full_inst | 13:34:17 | 16:56:59 | **3 小时 23 分**（10.2 min/ep） |

→ 单任务两轨道 ≈ **4.3 小时**（本任务 oracle 成功率高所以偏快；失败率高的任务会更慢）。

---

## 4. 与其它口径的关系（不要混）

| 数据 | 来源 | 能不能混进 760 |
| --- | --- | --- |
| 本次 18/20、8/20 | base 42，N=20，独立目录 | ✅ 正式数据 |
| 之前 probe 5/5、0/3 | **base 45**，N=5 | ❌ 只是可行性探测，已隔离在 `probe/` |
| Phase 2 Gate C 的 3/3 | base 42，N=3 | ❌ 旧口径，仅历史参考 |

---

## 5. 验收结论：**PASS**

四条批准条件全部满足，执行链路（分片调度 → 独立目录 → 统计 → 台账 → 崩溃码保留）跑通。
**批准进入剩余 640 次**。

同时登记两个偏差（照实写，不修饰）：
- oracle 90% 高于论文 75%（+15 pp）；
- full_inst 40% 高于论文 20%（+20 pp）。

这两个数与 living/office 的方向一致（oracle 偏高、full 接近或偏高），进一步支持
"公开 checkpoint 强于论文所用模型或 seed 分布不同"的解释，而不是"我们的实现有 bug"。

---

## 6. 第二阶段：5 卡分片（已启动）

| shard | GPU | 组合数 | 首个任务 |
| --- | ---: | ---: | --- |
| 1/5 | 0 | 8 | oracle_hse/arrange_sign |
| 2/5 | 1 | 6 | oracle_hse/bedside |
| 3/5 | 2 | 5 | oracle_hse/store_display |
| 4/5 | 3 | 6 | oracle_hse/checkout_counter |
| 5/5 | 4 | 7 | oracle_hse/counter_cleanup |

合计 **32 个 (track,task) 组合 = 640 eps**，与 760−80−40 吻合。

**启动阶段踩到并修掉的两个坑（已写进脚本）**：
1. `wait_gpu_free` 原本只看 GPU0，导致 2–5 号卡的 shard 永久等待 → 改为 `nvidia-smi -i $CUDA_VISIBLE_DEVICES`。
2. `flock` 的 fd 被 `sleep` 子进程继承，`kill -9` 主进程后锁仍被持有 → 子进程统一 `9>&-` 关闭锁 fd。
