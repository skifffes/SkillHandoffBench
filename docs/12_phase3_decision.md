# 12 · Phase 3A 决策

日期：2026-11-07。预算：**24 次 rollout 上限，实际 24 次尝试**（4 Gate B + 10 Gate C + 5 Gate D desk
+ 4 Gate D office + 1 次启动即崩的补跑）。

---

## 1. 汇总表（所有比例 = 分子/分母）

| Task | B0 Atomic Success | A→B Stage 1 | A→B Transition Conversion | Main Failure | Evidence for State Gap |
| --- | --- | --- | --- | --- | --- |
| `desk_arrange_2tasks` | **4/5**（`place_phone_stand`） | **5/5** | **5/5** | 新状态上**无失败**；已知失败 seed 4300003 仍 0/3 | **无**（失败交接状态未采样） |
| `office_organize_2tasks` | **5/5**（`stamp_seal`） | **4/4** | **4/4** | 新状态上**无失败**；已知失败 seed 4300000 仍 0/3 | **无**（同上） |
| 已知失败复查（不计入新状态） | — | desk 3/3、office 3/3 | **0/3、0/3** | S1 完成（42 / 41 步）后 S2 在 1458 / 1459 步内从未完成 | 无（Gate B 未开 trace） |

口径说明：
- `B0 Atomic Success` = 官方原子任务 env 的 `total_successes/total_episodes`（`docs/09 §4`）。
- `A→B Stage 1` = 该任务第二阶段任务中第一阶段完成的比例；`Transition Conversion` = 第二阶段成功 / 第一阶段成功。
- 两个任务的 seed 集合不同（`docs/10 §1`），**不可跨任务配对**。

---

## 2. 决策：**PIVOT**

理由按任务书的三个条件逐条对照：

| 条件 | 结果 |
| --- | --- |
| 下游 B 有可测的独立执行能力 | ✅ 满足（4/5、5/5，且步数 129–337，不是"勉强成功"） |
| A→B 中存在**可重复**的下游失败 | ⚠️ 只在**固定 seed**（4300003 / 4300000）上可重复（各 3/3），新状态 **0/9 失败** |
| 状态记录支持设计**可证伪**的状态干预 | ❌ 不满足：失败交接时刻**没有任何状态数据**（`docs/11 §1`） |

→ 三个条件只满足一个半，且"新状态不存在足够可研究的交接瓶颈"正好命中 **PIVOT** 的定义。

**不是 BLOCKED**：B0 入口合法可跑、完整性 14/14 通过、评测稳定（同 seed 逐位可重复）。
**也不是 GO**：GO 需要"可重复的下游失败 + 支持设计的失败状态记录"，后者缺失。

### 2.1 为什么不是 INCONCLUSIVE

- 新状态失败率 **0/9**（desk 5/5、office 4/4）；0/9 的 95% 置信上界约 **28%**。
- 也就是说：**"有一个常见的、稳定复现的交接瓶颈"这个假设，被数据直接否掉了**；
  但不能排除"发生率 <28% 的偶发瓶颈"。
- 若实验室要把上界压到 10%，按 0 失败计算需要 **≈29 个连续成功**（`0.9^29 ≈ 0.047`），
  即每任务再补 ~20 个新 seed、共 ~40 次 rollout。以本轮 24 次/5 小时的吞吐，约需 1.5 天。
  **本报告中不声称这件事已经做完。**

---

## 3. 五个问题的回答

**1. Motus 是否真正掌握这两个下游原子技能？**
是，**有条件地是**：`place_phone_stand` 4/5、`stamp_seal` 5/5，成功 episode 只用 45–336 步。
不是"每个初始状态都行"（各有 1 个 seed 失败/无解），但**远高于组合任务里的 0/3**，所以
"A→B 失败 = 策略根本不会做这个技能"这个解释被排除。

**2. 已知失败能否重复？**
能，**逐位重复**：`desk_arrange 4300003` 与 `office_organize 4300000` 各重复 3 次（Phase 2 一次 + Gate B 两次），
每次都是 1500 步触顶、S1 在 42 / 41 步完成、switch 在 48 步、S2 从未完成。
仿真在固定 checkpoint 下是确定性的，这不是噪声。

**3. 失败主要与状态、动作缓存、物体几何还是策略自身有关？**
**本轮不能判定**，但可以把范围缩小：
- 不是"策略不会"（B0 4/5、5/5）；
- 不是"缓存没清"导致的必然卡死（新状态 9/9 成功，而它们的 cue→switch 延迟同样有 1–39 步）；
- 失败**只在特定场景布局**上出现 → 更可能是**该场景几何 + 该场景下的交接位姿**共同作用，
  但**这两者本轮没有解耦**（`docs/09 §2.4`、`docs/11 §4` 干预 III）。

**4. 是否有证据值得下一轮执行物理位姿连接？**
**没有足够证据**。目前的证据只支持"存在两个可复现的、场景相关的失败"，
不支持"机器人交接位姿是原因"。要做物理位姿连接，必须先补上两件事（各 2–3 次 rollout）：
① 失败 seed 的交接状态 trace；② `clear_cache=true` 的对照。

**5. 下一轮最值得实现的一个最小干预是什么？**
**切换时机干预**（零代码改动）：对两个失败 seed 各跑 `--clear_cache true`（立即切换）
与 `false` 各 3 次。它只用官方配置项，直接隔离"陈旧 A 动作"，且结果二值可判。
如果这一步就消除了失败，那连几何 handoff 都不需要；如果没消除，再上"回中"（干预 II）。

---

## 4. 本轮**没有**做的事（边界）

- 没有实现 Agent / DeCo / GSC / GFC；
- 没有做几何 handoff，没有改机器人初始位姿；
- 没有训练、没有下载新模型；
- 没有修改任何官方成功判据；
- 没有覆盖历史运行（`results/phase2` 原样保留，Phase 3 写在新目录）；
- 没有 push。

## 5. 交付物

| 文件 | 内容 |
| --- | --- |
| `docs/09_atomic_b_competence.md` | Gate A 完整性审计 + B0 入口合法性论证 + B0 结果 |
| `docs/10_new_seed_transition_analysis.md` | 新 seed 的 A→B 条件成功率、cue→switch、B 首动作/首接触 |
| `docs/11_handoff_state_gap_evidence.md` | 状态差异证据（含"没有证据"的说明）+ 三个可证伪干预设计 |
| `docs/12_phase3_decision.md` | 本文件 |
| `scripts/run_phase3.sh` | Gate B/C/D 启动器（`b` / `c` / `d`） |
| `scripts/run_phase3_retry_office.sh`、`run_phase3_office_tail.sh`、`run_phase3_office_last.sh` | office_organize 因规划卡死的拆分补跑 |
| `scripts/check_phase2_integrity.py` | Gate A 完整性检查（5 个字段分开判定） |
| `scripts/analyze_phase3.py` | trace + 官方统计 → 交接状态表 |
| `results/phase3/` | 原始 stats、run.log、trace JSONL、analysis CSV、seed 文件、runs.jsonl |
