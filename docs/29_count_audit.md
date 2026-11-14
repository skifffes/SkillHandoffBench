# 29 · Episode 计数审计（B0 验收前硬门槛）

日期：2026-11-14。脚本：`scripts/audit_episode_count.py`；结果：`results/paper_table1/count_audit.json`。

> 本文回答验收时提出的计数矛盾：**为什么报告里是 669，而 18×2×20 + 15 = 735？**
> 结论：**669 是我算错了**；真实的"有效完整样本"是 **720**，另有 **14 个零散部分记录**，
> 且 `office_organize` 的续跑目录存在**重复 seed 的记录污染**，必须排除。

---

## 1. 三个数字的关系

| 数字 | 含义 | 是否可用 |
| ---: | --- | --- |
| **669** | 我上一版报告里的数。来源：8 天前某次 `paper_table1_status.sh` 快照（654）+ 后续 office 的 15 → 直接相加 | ❌ **错误**。654 是"当时尚未跑完"的中间态，之后有 6 个 pair 补满 20，我未重算 |
| **734** | 逐 pair 取"唯一种子数最多的那次 run"后求和（36×20 + 7 + 7） | ⚠️ 是**记录总数**，但含 14 个无法构成 20-episode 样本的部分结果 |
| **720** | 36 个 pair × 20 eps，全部 **20 unique seeds / 0 重复 / 0 中断** | ✅ **有效完整样本** |

**B0 的正确表述**：
- 有效完整样本 **720 / 760（94.7%）**；
- 未完成的 40 个 slot **全部集中在 `office_organize`**（2 轨道 × 20）；
- 任务级：**18 / 19 任务完成**，pair 级 **36 / 38 完成**。

---

## 2. 逐 pair 审计表（38 行）

| Track | Task | canonical n | unique seeds | dup | aborted | 其他 run |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| full | arrange_sign | 20 | 20 | 0 | 0 | 3 |
| full | bakery_close | 20 | 20 | 0 | 0 | 0 |
| full | bedside | 20 | 20 | 0 | 0 | 0 |
| full | breakfast_prep | 20 | 20 | 0 | 0 | 0 |
| full | checkout_counter | 20 | 20 | 0 | 0 | 0 |
| full | counter_cleanup | 20 | 20 | 0 | 0 | 0 |
| full | desk_arrange | 20 | 20 | 0 | 0 | 0 |
| full | hobby_desk | 20 | 20 | 0 | 0 | 0 |
| full | kitchen_switch | 20 | 20 | 0 | 0 | 0 |
| full | living_room_tidy | 20 | 20 | 0 | 0 | 0 |
| full | office_desk | 20 | 20 | 0 | 0 | 0 |
| full | **office_organize** | **7** | 7 | 0 | 0 | 4 |
| full | reception_desk | 20 | 20 | 0 | 0 | 0 |
| full | room_comfort | 20 | 20 | 0 | 0 | 0 |
| full | smart_home | 20 | 20 | 0 | 0 | 0 |
| full | stationery_sort | 20 | 20 | 0 | 0 | 0 |
| full | store_display | 20 | 20 | 0 | 0 | 0 |
| full | tabletop_arrange | 20 | 20 | 0 | 0 | 0 |
| full | workspace_setup | 20 | 20 | 0 | 0 | 4 |
| oracle | arrange_sign | 20 | 20 | 0 | 0 | 0 |
| oracle | bakery_close | 20 | 20 | 0 | 0 | 0 |
| oracle | bedside | 20 | 20 | 0 | 0 | 0 |
| oracle | breakfast_prep | 20 | 20 | 0 | 0 | 0 |
| oracle | checkout_counter | 20 | 20 | 0 | 0 | 0 |
| oracle | counter_cleanup | 20 | 20 | 0 | 0 | 0 |
| oracle | desk_arrange | 20 | 20 | 0 | 0 | 0 |
| oracle | hobby_desk | 20 | 20 | 0 | 0 | 0 |
| oracle | kitchen_switch | 20 | 20 | 0 | 0 | 0 |
| oracle | living_room_tidy | 20 | 20 | 0 | 0 | 0 |
| oracle | office_desk | 20 | 20 | 0 | 0 | 0 |
| oracle | **office_organize** | **7** | 7 | 0 | 0 | 4 |
| oracle | reception_desk | 20 | 20 | 0 | 0 | 0 |
| oracle | room_comfort | 20 | 20 | 0 | 0 | 0 |
| oracle | smart_home | 20 | 20 | 0 | 0 | 0 |
| oracle | stationery_sort | 20 | 20 | 0 | 0 | 0 |
| oracle | store_display | 20 | 20 | 0 | 0 | 0 |
| oracle | tabletop_arrange | 20 | 20 | 0 | 0 | 0 |
| oracle | workspace_setup | 20 | 20 | 0 | 0 | 4 |

- **36 个 pair：20 eps / 20 unique seeds / 0 重复 / 0 中断** → 720 条有效样本。
- "其他 run"列 = 同一 pair 的其它 attempt 目录数（重试用），不参与计数。

---

## 3. `office_organize` 的记录污染（必须排除）

| 目录 | metadata `total_episodes` | `episode_details` 记录数 | unique seeds | 判定 |
| --- | ---: | ---: | ---: | --- |
| `full/oracle_hse/office_organize_2tasks/attempt1`（续跑目录） | **8** | **3** | **3** | ❌ 元数据与明细不一致，且重复 seed |
| `full/batch3/full_inst/office_organize_2tasks/attempt1`（续跑目录） | **7** | **6** | 6 | ❌ 同上，少 1 条明细 |
| `shard5of5/.../oracle/attempt1`（干净部分） | 7 | 7 | 7 | ⚠️ 干净但只有 7/20 |
| `shard4of5/.../full/attempt1`（干净部分） | 7 | 7 | 7 | ⚠️ 干净但只有 7/20 |

**根因**：08:16 我对 `office_organize` 做了**原地续跑**（复用同一个 `save_dir`）。
`eval_policy` 续跑时只把**成功**的 seed 从候选里剔除，失败的 seed 会被**重新抽到并重跑**，
于是同一 seed 出现多条 `episode_details`；而 `total_episodes` 是累加计数器，两者对不上。

**这是我的操作失误**，已在此记录。后续 supervisor 已改为**永远新建 `attempt{n+1}` 目录**
（`scripts/run_all_paper_table1.sh` 的 attempt 递增逻辑），不允许原地续跑。

因此 `office_organize` 的正确状态是：
- **没有任何有效的 20-episode 样本**；
- 存在 7 + 7 个干净的**部分** episode（unique seeds），可作定性参考，**不进入任何平均值**；
- 剩余 26 个 slot 未跑。

---

## 4. 对 `docs/25` 的更正

| 原写法 | 更正为 |
| --- | --- |
| "完成度 669/760（88%）" | **有效完整样本 720/760（94.7%）**；另有 14 个 office 部分记录，不计入 |
| "18×2 = 720 eps 全部跑满 20" | 保持（已审计：20/20 unique，0 重复，0 中断） |
| "office 8/20、7/20" | **改为"无有效样本；7+7 部分记录；续跑目录记录不一致，已排除"** |

---

## 5. 验收口径（按提议冻结）

| 项目 | 状态 | 可验收 |
| --- | --- | --- |
| 18 任务 × 2 轨道的 Full Inst / Oracle HSE | 720 eps，每 pair 20/20 unique | ✅ |
| `office_organize` | 无有效样本，阻塞任务 | ❌ 未完成 |
| Ordered / Env 指标 | 分别统计，事件语义有 `docs/27`、`docs/28` 诊断 | ✅ |
| 公开模型与协议 | checkpoint 哈希、代码 SHA、协议锁均有核验 | ✅ |
| 论文 Table 1 精确复现 | seed 规则 / RoboTwin 版本 / max_steps / checkpoint revision 未核实 | ❌ 不能声称 |
| **B0 整体** | 公开代码协议下 18/19 任务复现 | **有条件验收** |

---

## 6. 复现

```bash
python3 scripts/audit_episode_count.py --root results/paper_table1 \
        --out results/paper_table1/count_audit.json
```

输出 `total`（记录总数 734）与 `pairs`（逐 pair 的 n / unique / dup / aborted）；
`short` 字段列出未满 20 的 pair（仅两个 office_organize）。
