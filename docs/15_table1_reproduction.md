# 15 · Table 1 复现结果（Motus：Full Inst / Oracle HSE）

状态：**Gate D 预检完成；Gate E 深跑（N=20）部分完成**。所有数字都是"分子/分母"，未经任何挑选。

---

## 1. 执行摘要

| 阶段 | 任务 | 轨道 | N | 结果 | 备注 |
| --- | --- | --- | --- | --- | --- |
| Gate D 预检 | living_room_tidy_2tasks | oracle_hse | 3 | **3/3** | 与 Phase 1（5/5）一致 |
| Gate D 预检 | office_desk_2tasks | oracle_hse | 3 | **3/3** | |
| Gate D 预检 | living_room_tidy_2tasks | full_inst | 3 | **1/3** | seed 4300002 成功 |
| Gate D 预检 | office_desk_2tasks | full_inst | 3 | **1/3** | |
| Gate E 深跑 | living_room_tidy_2tasks | oracle_hse | 20 | **4/12（跑到第 12 个 episode）** | 截止 21:30 未跑满 20，记 `INCOMPLETE` |
| Gate E 深跑 | office_desk_tasks | oracle_hse / full_inst | 20 | **未开始** | 时间不够 |

本轮新增 rollout = 预检 12 + 深跑 10 = **22 次**（不含 Phase 0–3A 历史运行）。

---

## 2. Gate D 预检（12 rollouts）——**协议链路已验证**

固定条件：Motus `Motus_robotwin2`(sha256 `70bc1741…`)、`--clear-cache false`、
`--max-steps-per-episode 1500`、`--episodes 3`、`--base-seed 42`、`robocombine_eval`（clean 场景）。

| Task | Track | 实际 seeds | 环境成功 | sr_ordered | 备注 |
| --- | --- | --- | --- | --- | --- |
| living_room_tidy_2tasks | oracle_hse | 4300000, 4300001, 4300002 | 3/3 | 3/3 | 与 Phase 1 同 seed 同结果 |
| office_desk_2tasks | oracle_hse | 4300000, 4300001, 4300002 | 3/3 | 3/3 | |
| living_room_tidy_2tasks | full_inst | 4300000, 4300001, 4300002 | 1/3 | 1/3 | 4300000/4300001 失败（1500 步触顶） |
| office_desk_2tasks | full_inst | 4300000, 4300001, 4300002 | 1/3 | 1/3 | |

**两轨道使用配对的初始状态**（同 seed 集），因此 oracle vs full 的差可直接归因于"指令/切换方式"。
`sr_ordered` 与环境成功在预检里数值相同（没有出现乱序完成）。

**完整性**：4 个 run 的 `evaluation_statistics.json` 均可解析、episode 数 = 请求数、
`_result.txt` 存在、`command.sh` 的 checkpoint/task/track 与预期一致。
退出码 `exit=1` 来自 runner 的"子进程非零"记账（子进程为 `-11` SIGSEGV，评测后析构崩溃，见 `docs/08 §6`），
**未**改写为 0。

---

## 3. Gate E 深跑（N=20，论文协议）

（本节在 21:15 后填入最终数字；只统计**跑完 20 个 episode** 的任务。）

**截止时间（21:30）到达时的真实状态**：

| Task | Track | 请求 N | 实际 N | env success | sr_ordered | ours % | paper % |
| --- | --- | ---: | ---: | --- | --- | ---: | ---: |
| living_room_tidy_2tasks | oracle_hse | 20 | **12**（INCOMPLETE） | 4/12 | 4/12 | **33.3** | 10.0 |
| office_desk_2tasks | oracle_hse | 20 | **0**（未开始） | — | — | — | 15.0 |
| living_room_tidy_2tasks | full_inst | 20 | **3**（仅预检那 3 次） | 1/3 | 1/3 | 33.3 | 5.0 |
| office_desk_2tasks | full_inst | 20 | **3**（仅预检那 3 次） | 1/3 | **0/3** | **0.0** | 10.0 |

逐 episode（living_room, oracle_hse, deep）：

| seed | 成功 | 步数 | s1_step | s2_step |
| --- | --- | ---: | ---: | ---: |
| 4300000 | ✅ | 173 | 51 | 125 |
| 4300001 | ✅ | 253 | 51 | 102 |
| 4300002 | ✅ | 465 | 51 | 102 |
| 4300003 | ✅ | 174 | 47 | 160 |
| 4300005 | ❌ | 1500 | 50 | — |
| 4300006 | ❌ | 1500 | 52 | — |
| 4300007 | ❌ | 1500 | 50 | — |
| 4300008 | ❌ | 1500 | 77 | — |
| 4300009 | ❌ | 1500 | 48 | — |
| 4300010 | ❌ | 1500 | 110 | — |
| 4300011 | ❌ | 1500 | — | — |
| 4300013 | ❌ | 1500 | — | — |

（4300004 被官方专家筛选跳过。）

**这条数据是本轮最重要的发现之一**：前 4 个 seed 全成、后 6 个 seed 全败，
失败形态完全一致（S1 在 47–110 步完成，之后 1390+ 步 S2 从未完成）。
说明 **living_room 的成功率高度依赖 seed**，Phase 1 报的 5/5 是"前 5 个 seed 恰好都好"的结果。

**注意 office_desk 的 full_inst**：环境成功 1/3，但 `sr_ordered = 0/3` ——
那个成功 episode 是**先完成 S2 再完成 S1**（乱序），按官方定义**不算 ordered success**。
这正是 `docs/13` §1 第 12 条强调的区别。

---

## 4. 19 任务全表（论文 vs 我们）

**本轮未完成 19×20。** 下表只填论文数值，我们的列在完成的格子里填数（其余标 `not run`）。

| Task | Paper Full | Ours Full | Paper Oracle | Ours Oracle | Difference (Oracle) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Arrange Sign | 0 | not run | 10.0 | not run | — |
| Bedside | 30.0 | not run | 30.0 | not run | — |
| Breakfast Prep | 20.0 | not run | 75.0 | not run | — |
| Checkout Counter | 15.0 | not run | 30.0 | not run | — |
| Counter Cleanup | 15.0 | not run | 15.0 | not run | — |
| Desk Arrange | 5.0 | not run | 10.0 | not run | — |
| Hobby Desk | 15.0 | not run | 35.0 | not run | — |
| Living Room Tidy | 5.0 | 1/3 (n=3) | 10.0 | **4/12** (INCOMPLETE) | **+23.3** |
| Office Desk | 10.0 | **0/3**（1 次环境成功但乱序） | 15.0 | 3/3 (n=3, 预检) | +85.0 |
| Office Organize | 15.0 | not run | 15.0 | not run | — |
| Reception Desk | 5.0 | not run | 15.0 | not run | — |
| Stationery Sort | 10.0 | not run | 10.0 | not run | — |
| Store Display | 5.0 | not run | 20.0 | not run | — |
| Tabletop Arrange | 20.0 | not run | 0 | not run | — |
| Workspace Setup | 15.0 | not run | 50.0 | not run | — |
| Bakery Close | 5.0 | not run | 35.0 | not run | — |
| Kitchen Switch | 0 | not run | 0 | not run | — |
| Room Comfort | 0 | not run | 0 | not run | — |
| Smart Home | 0 | not run | 0 | not run | — |

**不要把这张表当成 Table 1 的复现**：19 个任务里我们只跑了 2 个，且 full_inst 只有 n=3。

---

## 5. Ordered HSE（Gate G）

**`ORDERED_HSE_BLOCKED`**：

- 论文附录 C.3：progress predictor = **Florence** 编码器（1024 维特征）→ 2 层 GRU(256) → MLP 256→128→1 → sigmoid；
  训练用 tanh 目标（center 0.5, slope 0.1）、Huber δ=0.1、val_acc@10%。
- 公开 runner 的接口是 `--real-predictor-bundle-dir`（"standalone XVLA predictor bundle"）+
  `--real-xvla-model-dir`（X-VLA-RoboTwin2 backbone）——**backbone 与论文写的 Florence 不一致**。
- 本地：**没有** XVLA predictor bundle，**没有** X-VLA 权重；论文也**没有**公开这两者的下载地址/训练代码。
- 因此本轮**不跑** ordered_hse，也不拿别的 VLM 冒充。

→ 需要作者提供：predictor bundle 的定义（backbone/维度/阈值）+ 训练好的权重。

---

## 6. 复现命令（可重跑）

```bash
cd /scratch/lijh/SkillHandoffBench
# Gate D（12 rollouts）
bash scripts/run_paper_reproduction.sh preflight oracle_hse
bash scripts/run_paper_reproduction.sh preflight full_inst
# Gate E（2 任务 × 20 episodes；分批）
bash scripts/run_paper_reproduction.sh deep oracle_hse
bash scripts/run_paper_reproduction.sh deep full_inst
# 完整性 + 论文对照
python scripts/check_paper_reproduction.py --root results/paper_table1 --track oracle_hse \
  --expected-episodes 20 --log-glob 'logs/paper_table1/*.log' --json results/paper_table1/check_oracle.json
```
