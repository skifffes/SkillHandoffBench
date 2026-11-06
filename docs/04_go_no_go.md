# 04 · GO / PIVOT / BLOCKED

**结论：`GO`（有条件）** —— RoboCombine + Motus 在本机**真的能跑**，并且已经产出一个
checkpoint-backed、官方判据下的两阶段组合任务成功 episode。条件见 §6。

机器：`222.29.51.96`，单卡 A40，2026-11-06 22:54 → 2026-11-07 01:30（CST）。
详细执行记录见 `docs/03`，逐项可行性判定见 `docs/01`，指标口径见 `docs/02`。

---

## 1. 实际完成了什么

| 交付 | 状态 | 证据 |
| --- | --- | --- |
| RoboCombine 代码固定到 commit | ✅ | `df237b22bd5c39d705b103daf2b9a8a168c9d453`（2026-10-15） |
| 10 项可行性逐条判定（AVAILABLE/MISSING/INCOMPATIBLE/UNVERIFIED） | ✅ | `docs/01 §1` |
| 体积/磁盘审计（先审计后下载） | ✅ | `docs/01 §4`：必需 ≈53 GB；`/scratch` 232→约 150 GB 剩余 |
| 隔离运行环境（不碰旧环境） | ✅ | `envs/motus`（py3.10.21 / torch 2.4.1+cu121 / sapien 3.0.0b1 / transformers 5.0.0rc0） |
| Gate 1：任务列表 / 契约测试 / import / sha256 / 渲染 | ✅ | 19 任务；**38 passed in 2.43s**；`RENDER OK`；sha256 `70bc1741…` |
| 仿真栈 smoke（资产+embodiment+CuRobo+SAPIEN） | ✅ | `logs/sim_smoke.log`：专家 demo 双阶段成功 |
| **Gate 2：Motus + oracle_hse 真实 rollout** | ✅ **1/1 成功** | `results/gate2_20261107_010606_*/` |
| **Gate 3：2 任务 × 5 episodes** | ✅ **9/10 成功**（5/5 + 4/5）；阶段1 **10/10**、切换 **10/10** | `results/gate3a_20261107_012314_*/`、`results/gate3b_20261107_013845_*/` |
| 可复现脚本 | ✅ | `scripts/{fetch_assets,fetch_models,fetch_wan,setup_motus_env,setup_motus_env_v2,fix_env,setup_x11,setup_nvcc,build_curobo076,build_curobo_retry,run_smoke,test_task_env,make_results}.sh\|py` |
| 官方源码改动审计 | ✅ | `docs/patches/001..002`（共 2 个 patch，均不触碰判据/切换逻辑） |

### 1.1 Gate 2 的关键数字（可直接引用）

```
task          living_room_tidy_2tasks   (Place cup on coaster -> Place fan on pad)
track/policy  oracle_hse / Motus
checkpoint    Motus_robotwin2 (16,046,580,367 B, sha256 70bc1741b45db5e3eae86510ad3bb1bd1aef04f10b17d8c1ff4dbe099300eb65)
clear-cache   false
seed          4,300,000
result        1/1 success, 173 steps (limit 1500)
stage-1 done  step 51
switch        step 64   source="gt"  from 0 -> 1  cache_cleared=false
stage-2 done  step 125
episode time  141.8 s (setup 37.5 s, inference 103.7 s), GPU peak ~38.8/46.8 GB
```

**一个值得记录的行为**：完成信号在第 **51** 步出现（`cue_step=51`），但实际切换到第 **64** 步
（`switch_step=64`），差值 13 步 —— 这正是 `--clear-cache false` 的语义：**保留当前 action chunk，
等它跑完再换指令**。如果用默认的 `--clear-cache true`，这个差值应接近 0。这直接证明
`--clear-cache` 被正确固定、且切换时机可观测（`docs/02 §5` 的要求）。

### 1.2 Gate 3 的关键数字（可直接引用）

| 指标 | living_room_tidy_2tasks | office_desk_2tasks | 合计 |
| --- | --- | --- | --- |
| Ordered success | **5/5 = 1.00** | **4/5 = 0.80** | **9/10 = 0.90** |
| Stage-1 success | 5/5 | 5/5 | **10/10 = 1.00** |
| Transition conversion | 5/5 | 5/5 | **10/10 = 1.00** |
| Downstream skill success | 5/5 | 4/5 | **9/10 = 0.90** |
| 平均 episode 时间 | 141 s | 164 s | — |
| cue→switch 差值 | 13,13,13,1,14 | 5,1,4,15,15 | 1–15 步 |

唯一的失败是 `office_desk_2tasks` seed `4300003`：**阶段 1 成功、切换也发生**（cue 177 → switch 192），
但下游技能在 1500 步预算内没完成（`timeout`）。这不是"没切换"，也不是夹爪判据问题，
属于 `docs/02 §4` 的 Downstream Skill Success 失败 —— 正是 B4–B7 要改善的那一类。

---

## 2. 哪些失败 / 不可验证

| 项 | 判定 | 依据 | 最小解决措施 |
| --- | --- | --- | --- |
| **Ordered HSE（B2）** | **MISSING** | `eval_policy.py:534-549` 需要 X-VLA predictor bundle + 模型；仓库只带 `xvla_progress_predictor/` 代码骨架，权重未发布、本机也没有 | 从论文/作者获取 predictor bundle + `X-VLA-RoboTwin2` 权重（体积未公布），或先用 1 个任务人工标注少量帧复现阈值规则 |
| **pi05（B0/B1 的另一策略）** | **INCOMPATIBLE** | adapter 要 `pi05_aloha_full_base`（3 相机/14 维动作/`checkpoint/assets/<id>`）；手上只有 `pi05_droid`（DROID 单相机/8 维） | 下载官方 `pi05_aloha_full_base` checkpoint（另需 curobo 已就绪，本机已满足） |
| **B4–B7（交接状态选择本体）** | **未实现（本轮按计划不做）** | `docs/02 §9` 只给了仪器方案 | 下一步实现只读状态旁路采样 + 规划器接口 |
| **图像-状态时序** | UNVERIFIED（沿用 Simulate 4.7 的 PARTIAL） | `docs/00_simulate_4_7_audit.md §4.5` | 与 robocombine 无关；要用自己的图像管线时再验证 |
| **RoboTwin 资产许可证** | UNVERIFIED | HF 数据集页未声明 | 不外传、不重分发；内部使用 |
| **原子技能成功率（B0）** | 部分 | 本轮只测了 2 个任务的组合，未做 19 任务单技能扫描 | 用同一套 harness 跑 `full_inst` 或单阶段 env |

**没有做的、也不打算含糊过去的**：
- 没有跑 19 任务全量；
- 没有训练（红线 4）；
- 没有改判据（红线 3），只打了 2 个运行性 patch；
- Gate 3 若因 30–45 分钟上限被截断，会在 `docs/03 §4` 明确写"未完成 n 个 episode"，不会用部分结果冒充全量。

---

## 3. 是否建议暂停 Simulate 4.7

**建议暂停。** 依据（全部来自 `docs/00`）：
- 4.7 的契约验收已完成并提交（`55fca58`），暂停不丢信息；
- C 层（冻结 VLA 从独立初始状态自主成功）严格成功率 **0**，且 4.2–4.6 已排除"数据量/参数范围/步数"是主因；
- D 层（A→B 组合）**从未运行**，而它才是交接研究的对象；
- 继续在 Simulate 上加码，边际收益低于把同样的算力放到 RoboCombine 的可组合任务上。

唯一值得回头做的两件小事（与本研究互补）：图像-状态时序逐帧验证、终态精度专项。

---

## 4. 是否建议 Motus + RoboCombine

**建议。** 三条硬证据：
1. 官方 checkpoint 在本机**真跑通**了两阶段任务（1/1），且切换事件、阶段完成步、失败分类全部有结构化记录；
2. 资产/环境/规划器**已经就位并验证过**（`logs/sim_smoke.log`、Gate 1），第二次跑不需要再解决环境问题；
3. 成本可接受：单 episode ≈ 142 s（173 步）；1500 步的最坏情况 ≈ 10 min/episode；
   A40 单卡即可（峰值 38.8 GB，Motus 官方要求 41 GB 档）。

代价与风险（必须一起说）：
- 环境适配花了约 **2.5 小时**（12 项坑，见 `docs/01 §9`），换机器要重来一遍；
- `ordered_hse` 缺 predictor → 目前**只能做 oracle_hse 与 full_inst 两条 track**；
- 数据/权重共 **53 GB**，换机器要考虑磁盘。

---

## 5. 是否值得进入 handoff-state selection（B4–B7）

**值得，但有前置条件。** 

支持理由：harness 已经能给出"阶段完成步 / 切换步 / 是否成功 / 每阶段失败原因"的逐 episode 记录
（`evaluation_statistics.json::episode_details`），B4–B7 只需要在同一位置**追加**交接瞬间的
`qpos / 末端位姿 / 物体位姿`，不需要改判据。

前置条件（缺一不可）：
1. 先用 Gate 3 的数据确认**原子成功率足够高**（否则组合评测的失败主要来自单技能，交接信号被淹没）；
2. 固定任务集合与 seed 集合（`docs/02 §3`），不允许为改善结果换任务；
3. B5/B6/B7 共用同一候选位姿集合与同一规划预算（`docs/02 §2.1`）；
4. oracle_hse 的"特权信号"必须写进报告的局限（它不是视觉 Agent）。

---

## 6. 下一轮最小必要任务（按优先级）

| # | 任务 | 为什么 | 预估 |
| --- | --- | --- | --- |
| 1 | 加 `full_inst` 对照（同任务同 seed） | B1 基线，且能验证"长指令 vs 分阶段"的差异 | 20–30 min |
| 2 | 状态旁路采样 wrapper（只读），产出 `handoff_record.jsonl` | B4–B7 的仪器前提 | 2–3 h |
| 3 | B4（直接交接）与 B6（几何连接） | 第一个有意义的对照 | 3–4 h |
| 4 | 把 `office_desk_2tasks` seed 4300003 的失败（下游超时）单独复跑 3 次 | 判断它是偶发还是系统性下游瓶颈 | 15–20 min |
| 5 | （可选）申请 X-VLA predictor 权重，解锁 B2 | 让 Ordered HSE 可用 | 依赖外部资源 |

---

## 7. 最终判断

### `GO`

**理由（逐条对应证据）**
1. **真实模型跑通**：`results/gate2_20261107_010606_*` 里有 `1/1` 成功、seed `4300000`、
   173 步、阶段 1/2 完成步、切换事件（`source="gt"`, step 64）、`cache_cleared=false`；
   原始 `task.log` 与 `evaluation_statistics.json` 都在 `official/` 下。
2. **规模化了**：Gate 3 两个任务共 10 个 episode，**9/10 成功**；阶段 1 **10/10**、切换 **10/10**。
   唯一失败是下游超时（1500 步），不是原子能力缺失。
3. **判据没有被放宽**：成功来自官方 `check_success()`（位置/姿态阈值 + 夹爪开合），
   我们只打了 2 个运行性 patch（`docs/patches/`），没有改任何阈值或切换逻辑。
4. **环境可复现**：13 个脚本 + 12 项坑的根因与修复都写进了 `docs/01 §9` 与 `docs/03 §5`。
5. **诚实的边界**：ordered_hse 缺权重（MISSING）、pi05 不兼容（INCOMPATIBLE）、
   B4–B7 未实现——这些都写在 §2，不用"计划"冒充结果。

**PIVOT 触发条件全部未触发**（对照下表）：stage-1 成功率 100% ≫ 20%；
transition conversion 100% ≥ 50%；单 episode 最长 1500 步 ≈ 6–7 分钟 < 10 分钟。
因此**不触发 PIVOT**，可以直接进入 B4–B7。

### `PIVOT` 触发条件（预先写死，避免事后找理由；本轮实测值见括注）

| 条件 | 动作 | 本轮实测 |
| --- | --- | --- |
| Gate 3 中 `stage-1 success rate < 20%`（任一任务） | 暂停组合评测，先做 B0（单技能）与任务筛选；或换成功率更高的任务对 | **100% / 100%** → 未触发 |
| Gate 3 中 `transition conversion < 50%`（进入第二阶段的 episode 比例） | 说明切换/指令传递有问题，先诊断 HSE 而非加交接状态 | **100%** → 未触发 |
| 单 episode 墙钟 > 10 min（1500 步触顶且极慢） | 降 `--max-steps-per-episode` 前必须先确认这不改变判据语义；否则换任务 | 最长 1500 步 ≈ 6–7 min → 未触发 |

### `BLOCKED` 情形

本轮**不是** BLOCKED。若换到新机器，最可能阻断的是：无 CUDA toolkit（需要 nvcc）、
glibc <2.27（warp/open3d 装不上）、无 X11（SAPIEN 起不来）、磁盘 <60 GB。
这四项都有对应的用户空间绕法，已记录在 `docs/01 §9`。
