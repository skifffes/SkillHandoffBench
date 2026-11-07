# 06 · Full Instruction 对照（Gate B）

运行时间：2026-11-07 10:30–12:25 CST。机器：A40 单卡（0 号），同一台服务器、同一 venv、同一 checkpoint。

---

## 1. 目的与边界

**只回答一个问题**：在同一批初始状态上，"一句长指令贯穿全程"（`full_inst`）与
"Oracle 技能切换"（`oracle_hse`）差多少。

**不做**：不证明"交接状态方法有效"（本轮没有实现任何交接状态方法）；不改变判据；
不把结果当成论文 Table 1 的复现（见 `docs/05`）。

---

## 2. 受控变量

| 项 | 取值 | 与 Phase 1 一致？ |
| --- | --- | --- |
| checkpoint | `Motus_robotwin2`，sha256 `70bc1741…`，16,046,580,367 B | ✅ |
| policy | `Motus`（冻结） | ✅ |
| 任务 | `living_room_tidy_2tasks`、`office_desk_2tasks` | ✅ |
| 初始状态 | `--base-seed 42` → seed `4300000..4300004`（同 seed ⇒ 同 `setup_demo` 场景） | ✅ |
| 判据 | 官方 `check_success()`，未改 | ✅ |
| 最大步数 | 1500 | ✅ |
| episode 数 | 每任务 5 | ✅ |
| clear-cache | `false` | ✅ |
| 单卡 | `CUDA_VISIBLE_DEVICES=0` | ✅ |

**唯一执行差异（自变量）**：`--track full_inst`。`run_split` 因此额外传
`--custom_instruction "…long…"`，并且**不会**产生 `switch_events`。

---

## 3. 实际命令与产物

```bash
cd /scratch/lijh/SkillHandoffBench
EPISODES=5 MAX_MINUTES=60 bash scripts/run_phase2.sh b2   # office_desk 段（见下方说明）
bash scripts/run_phase2.sh b                                # 两个任务（living 段在 11:27 被切分）
```

| 产物 | 路径 |
| --- | --- |
| living_room 原始 | `results/phase2/gateB_full_inst/robocombine/full_inst/Motus/20261107_103004_…/tasks/living_room_tidy_2tasks/` |
| office_desk 原始 | `results/phase2/gateB_office/robocombine/full_inst/Motus/20261107_112938_…/tasks/office_desk_2tasks/` |
| 汇总（合并两个 root） | `results/phase2/_summary/gateB/{tasks.csv,episodes.csv,summary.json}` |
| seed 计划（跑前落盘） | `results/phase2/seed_plan.json` |
| GPU/磁盘快照 | `results/phase2/system_snapshots.log` |

**过程说明（必须记录的偏差）**：原计划一次 `run_split` 跑完两个任务，但 living 段 5 个 episode
全部 1500 步触顶，预计会撞上 75 分钟总上限，因此在 living 完成 5/5 后主动切分，office_desk
用独立 invocation 重跑（同样的种子与参数）。副作用：living 那段**没有 `run_manifest.json`**
（manifest 在 run_split 结束时才写），其命令记录在 `tasks/living_room_tidy_2tasks/command.sh`
与 `logs/phase2_gateB_runner.log`。**这不是数据缺失**：逐 episode 的
`evaluation_statistics.json` 与 `task.log` 都在。

---

## 4. 结果

### 4.1 living_room_tidy_2tasks —— **1/5**

| seed | 成功 | 总步数 | S1 完成步 | S2 完成步 | Oracle HSE 同 seed |
| --- | --- | --- | --- | --- | --- |
| 4300000 | ❌ | 1500（触顶） | 48 | — | ✅ 173 步 |
| 4300001 | ❌ | 1500（触顶） | 111 | — | ✅ 253 步 |
| 4300002 | ✅ | 1115 | 49 | **158** | ✅ 465 步（s2@102） |
| 4300003 | ❌ | 1500（触顶） | 47 | — | ✅ 174 步 |
| 4300004 | ❌ | 1500（触顶） | 50 | — | ✅ 159 步 |

### 4.2 office_desk_2tasks —— **1/5**

| seed | 成功 | 总步数 | S1 完成步 | S2 完成步 | Oracle HSE 同 seed |
| --- | --- | --- | --- | --- | --- |
| 4300000 | ❌ | 1500（触顶） | 41 | — | ✅ 172 步 |
| 4300001 | ✅ | 736 | **655** | **359**（早于 S1） | ✅ 285 步 |
| 4300002 | ❌ | 1500（触顶） | **从未** | — | ✅ 423 步 |
| 4300003 | ❌ | 1500（触顶） | **从未** | — | ❌ 1500 步 |
| 4300004 | ❌ | 1500（触顶） | 56 | — | ✅ 206 步 |

### 4.3 汇总对照（**同 seed、同初始状态**）

| 指标 | full_inst | oracle_hse（Phase 1） |
| --- | --- | --- |
| ordered success | **2/10 = 0.20** | **9/10 = 0.90** |
| stage-1 success | 8/10 = 0.80 | 10/10 = 1.00 |
| stage-2 success | 2/10 = 0.20 | 9/10 = 0.90 |
| 平均步数（成功者） | 1115、736 | 173–465 |
| switch 事件 | 0（该 track 不产生） | 10/10 episode 各 1 次 |

> 两个 track 各有自己的分母（10 vs 10），**不合并**；这里并列只为对照。

---

## 5. 成功/失败轨迹的行为差异（`scripts/forensics_episode.py`，只读日志）

| 任务 | seed | 形态 | S1 首次完成 | S2 首次完成 | 最长 (S1,S2) 平台 |
| --- | --- | --- | --- | --- | --- |
| living | 4300000 | 第一阶段做完 → 再也不动 | 49 | 无 | (True,False) 1452 步 |
| living | 4300001 | 同上 | 112 | 无 | (True,False) 1389 步 |
| living | 4300002 | 两阶段都做完 → 夹爪不收 | 50 | 159 | (True,True) 957 步 |
| living | 4300003 | 第一阶段做完 → 再也不动 | 48 | 无 | (True,False) 1453 步 |
| living | 4300004 | 同上 | 51 | 无 | (True,False) 1444 步 |
| office | 4300000 | 第一阶段做完 → 再也不动 | 42 | 无 | (True,False) 1459 步 |
| office | 4300001 | **顺序颠倒**：先做 S2 再做 S1 | 656 | 360 | (False,True) 296 步 |
| office | 4300002 | **从未开始**（1500 步全 (False,False)，右夹爪一直 1.0） | 无 | 无 | (False,False) 1500 步 |
| office | 4300003 | **从未开始** | 无 | 无 | (False,False) 1500 步 |
| office | 4300004 | 第一阶段做完 → 再也不动 | 57 | 无 | (True,False) 1444 步 |

三条可直接引用的结论：

1. **主力失败模式是"第一阶段完成后不再继续"**（7/10 episode）：S1 在 41–112 步就完成，
   之后 1300+ 步里 S2 一次都没成立。这与 `oracle_hse` 在 cue 后立刻换指令形成鲜明对比。
2. **成功也可能"顺序颠倒"**：office seed 4300001 的 S2（`s2_step=359`）早于 S1（`655`）。
   官方判据只要求"所有子任务完成 + 夹爪张开"，**不检查顺序** —— 所以 `full_inst` 的
   "成功"并不等于"按指令顺序执行"。
3. **有 2 个 episode 连第一阶段都没做成**（office 4300002/4300003）—— 这是**原子能力/指令跟随**
   问题，而不是"第二阶段交接"问题。把它算进"交接失败"是错的。

---

## 6. 结论

1. 在这个 setting 下，**Oracle 技能切换显著优于一句长指令**：9/10 vs 2/10（同 seed、同模型、同判据）。
2. 差异的主要来源不是"下游技能不会做"，而是**第一阶段完成后，长指令没有把策略推进到第二阶段**
   （7/10 的 episode 卡在 (S1✓,S2✗)）。
3. 即使成功，`full_inst` 也慢得多（1115 / 736 步 vs 174–465 步），且可能**乱序完成**。
4. 本对照**只说明"切换指令有用"**，不能说明"交接状态选得好"——本轮没有改任何交接状态。
   下一轮（B4–B7）才是在**同样是 Oracle 切换**的前提下改变交接**状态**。

> **退出码说明**：本文件所有数字都取自 `evaluation_statistics.json`。所有 Phase 2 子进程都以 `code=-11`（SIGSEGV）结束，但那是 **main() 返回之后**的解释器析构崩溃（`_result.txt` 已写出、stats 完整），不影响指标，详见 `docs/08 §6`。

