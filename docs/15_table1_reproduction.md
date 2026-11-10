# 15 · Table 1 复现结果（Motus：Full Inst / Oracle HSE）

状态：**Gate D 预检完成；Gate E 深跑已完成 4 组（2 任务 × 2 轨道 × 20 episodes）**。
19 个任务里只跑了 2 个，其余 17 个未跑。所有数字都是"分子/分母"，未经挑选。

---

## 1. 执行摘要

| 阶段 | 任务 | 轨道 | N | 结果 | 备注 |
| --- | --- | --- | --- | --- | --- |
| Gate D 预检 | living_room / office_desk | oracle_hse | 3+3 | **6/6** | 与 Phase 1 同 seed 同结果 |
| Gate D 预检 | living_room / office_desk | full_inst | 3+3 | **2/6**（ordered 1/6） | office 那次成功是乱序 |
| **Gate E 深跑** | living_room_tidy_2tasks | oracle_hse | **20** | **7/20 = 35.0%** | paper 10.0% |
| **Gate E 深跑** | office_desk_2tasks | oracle_hse | **20** | **9/20 = 45.0%** | paper 15.0% |
| **Gate E 深跑** | living_room_tidy_2tasks | full_inst | **20** | **2/20 = 10.0%** | paper 5.0% |
| **Gate E 深跑** | office_desk_2tasks | full_inst | **20** | **2/20 环境成功、0/20 ordered = 0.0%** | paper 10.0% |

**本轮新增 rollout = 12（预检）+ 80（深跑）= 92 次**，全部保留退出码与原始日志。

---

## 2. 深跑结果（论文协议 N=20）

固定：Motus `Motus_robotwin2`(sha256 `70bc1741…`)、`--clear-cache false`、`--max-steps-per-episode 1500`、
`--episodes 20`、`--base-seed 42`、`robocombine_eval`（clean 场景）、单卡 A40。

| Task | Track | N | env success | **sr_ordered** | ours % | paper % | diff |
| --- | --- | ---: | --- | --- | ---: | ---: | ---: |
| living_room_tidy_2tasks | oracle_hse | 20 | 7/20 | **7/20** | **35.0** | 10.0 | **+25.0** |
| office_desk_2tasks | oracle_hse | 20 | 9/20 | **9/20** | **45.0** | 15.0 | **+30.0** |
| living_room_tidy_2tasks | full_inst | 20 | 2/20 | **2/20** | **10.0** | 5.0 | **+5.0** |
| office_desk_2tasks | full_inst | 20 | 2/20 | **0/20** | **0.0** | 10.0 | **−10.0** |
| **两任务合计** | oracle_hse | 40 | 16/40 | 16/40 | **40.0** | 12.5（两任务均值） | +27.5 |
| **两任务合计** | full_inst | 40 | 4/40 | 2/40 | **5.0** | 7.5（两任务均值） | −2.5 |

Wilson 95% 区间：oracle 40%（16/40）= `[26.0, 55.6]`；full 5%（2/40）= `[1.4, 16.4]`。

### 2.1 逐 episode

**oracle_hse / living_room（7/20）** —— 成功集中在 seed `4300000-4300003, 4300016, 4300019, 4300021`：

| seed | 成功 | 步数 | s1 | s2 |
| --- | --- | ---: | ---: | ---: |
| 4300000 | ✅ | 173 | 51 | 125 |
| 4300001 | ✅ | 253 | 51 | 102 |
| 4300002 | ✅ | 465 | 51 | 102 |
| 4300003 | ✅ | 174 | 47 | 160 |
| 4300016 | ✅ | 221 | 50 | 174 |
| 4300019 | ✅ | 175 | 48 | 120 |
| 4300021 | ✅ | 124 | 51 | 111 |
| 其余 13 个 | ❌ | 1500 | 48–110 | — |

**oracle_hse / office_desk（9/20）**：成功 seed `4300000,1,2,4,6,8,17,24,34`（步数 172–1104）；
失败 11 个全部 1500 步触顶。

**full_inst / office_desk（0/20 ordered）**：两个"成功"都是**乱序**——
`4300001`（s2@359 < s1@655）、`4300024`（s2@45 < s1@984）。按官方 `sr_ordered` 定义**都不算**。

### 2.2 与预检的对比（seed 选择的效应）

| living_room, oracle_hse | N | 成功 | 比例 |
| --- | ---: | ---: | ---: |
| 预检（seed 4300000–4300002） | 3 | 3 | 100% |
| 深跑（seed 4300000–4300021） | 20 | 7 | **35%** |
| 论文 | 20 | 2 | 10% |

前 4 个 seed 全成 → 预检自然 100%；把 seed 铺到 20 个，成功率回落到 35%，
**这就是为什么不能用 3–5 个 episode 的数字声称复现**。

---

## 3. 19 任务对照表

| Task | Paper Full | Ours Full | Paper Oracle | Ours Oracle | Diff (Oracle) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Arrange Sign | 0 | not run | 10.0 | not run | — |
| Bedside | 30.0 | not run | 30.0 | not run | — |
| Breakfast Prep | 20.0 | not run | 75.0 | not run | — |
| Checkout Counter | 15.0 | not run | 30.0 | not run | — |
| Counter Cleanup | 15.0 | not run | 15.0 | not run | — |
| Desk Arrange | 5.0 | not run | 10.0 | not run | — |
| Hobby Desk | 15.0 | not run | 35.0 | not run | — |
| **Living Room Tidy** | 5.0 | **10.0** (2/20) | 10.0 | **35.0** (7/20) | **+25.0** |
| **Office Desk** | 10.0 | **0.0** (0/20 ordered) | 15.0 | **45.0** (9/20) | **+30.0** |
| Office Organize | 15.0 | not run | 15.0 | not run | — |
| Reception Desk | 5.0 | not run | 15.0 | not run | — |
| Stationery Sort | 10.0 | not run | 10.0 | not run | — |
| Store Display | 5.0 | not run | 20.0 | not run | — |
| Tabletop Arrange | 20.0 | not run | 0 | not run | — |
| Workspace Setup | 15.0 | not run | 50.0 | not run | — |
| Bakery Close | 5.0 | not run | 35.0 | not run | — |
| Kitchen Switch | 0 | not run | 0 | not run | — |
| Room Comfort | 0 | not run | 0 | not run | — |
| Smart Home | 0 | not run | 5.0 | not run | — |
| **19 任务总体** | **10.0** | **未完成**（2/19 任务） | **19.7** | **未完成**（2/19 任务） | — |

**这不是 Table 1 的复现**：19 个任务只跑了 2 个。已完成的两行可以直接对照，其余 17 行是 `not run`。

---

## 4. Ordered HSE（Gate G）：`ORDERED_HSE_BLOCKED`

- 论文附录 C.3：progress predictor = **Florence** 编码器（1024 维）→ 2 层 GRU(256) → MLP 256→128→1 → sigmoid；
  tanh 目标（center 0.5 / slope 0.1）、Huber δ=0.1、val_acc@10%。
- 公开 runner 的接口是 `--real-predictor-bundle-dir`（"standalone XVLA predictor bundle"）+
  `--real-xvla-model-dir`（X-VLA-RoboTwin2 backbone）——**backbone 与论文写的 Florence 不一致**。
- 本地两者都没有，论文也未公开下载地址 → 本轮不跑，也不拿别的 VLM 冒充。

---

## 5. 复现命令

```bash
cd /scratch/lijh/SkillHandoffBench
bash scripts/run_paper_reproduction.sh preflight oracle_hse   # 12 rollouts
bash scripts/run_paper_reproduction.sh preflight full_inst
bash scripts/run_paper_reproduction.sh deep oracle_hse        # 2 任务 × 20
bash scripts/run_paper_reproduction.sh deep full_inst
python scripts/check_paper_reproduction.py --root results/paper_table1/gateE_deep \
  --track oracle_hse --expected-episodes 20 --json results/paper_table1/check_oracle_hse_deep.json
```
