# 30 · PRTI 官方方法复现审计（Phase B1）

日期：2026-11-14。范围：**只做静态审计，不启动训练、不启动大规模 rollout、不下载大文件**。
仓库：`third_party/RoboCombine` @ `df237b22bd5c39d705b103daf2b9a8a168c9d453`（= 官方远端 HEAD，已实测）。
审计脚本：`scripts/extract_prti_passages.py`（论文段落抽取，只读）。

---

## 1. Executive Summary

**结论：`BLOCKED`。**

PRTI 在论文里是一个**训练期（post-training）的数据分布方法**，不是推理期的状态搬运方法。
官方公开仓库**只包含评测代码**（`script/eval_policy.py` + `handoff_eval/`），
**没有任何 PRTI 实现**：

| 关键事实 | 证据 |
| --- | --- |
| 全仓搜索 `PRTI` / `pose.?robust` → **0 命中** | `git grep -niE "prti|pose.?robust"` = 0 |
| `script/` 只有 `eval_policy.py` | `Get-ChildItem script` |
| `policy/README.md` 明说："contains only policy adapter code... **does not include models, checkpoints, tokenizers, or runtime assets**" | `policy/README.md` 第 3–5 行 |
| README 公开范围：19 任务 / 3 轨道 / 2 policy，且 "**Evaluation code** ... is available now" | `README.md` 第 40–60 行 |
| 论文的 PRTI 需要 **π0.5 RoboTwin atomic checkpoint** + **~10K episodes / 2M frames** 单技能数据 + **50K steps / 4 accelerators** | 论文 App. D |
| HF 上没有 PRTI / RoboCombine 权重；`AutoLab-SJTU` 名下只有 CasaMeastro / SurroundNEXO / GSR | HF API 查询 |

因此：**Level 1（静态审计）可达；Level 2（推理复现）不可达**，因为连 PRTI 的权重都不存在公开来源，
而"从头复现 PRTI"又缺少训练代码与训练数据。

---

## 2. Paper Method Extraction

> 说明：本审计的论文文本由 PDF 抽取，**页码未保留**，因此引用到**章节 / 公式 / 表 / 附录**级别。
> 抽取脚本：`scripts/extract_prti_passages.py`（可复跑）。

### 2.1 它是解决什么问题的

- 论文提出 **start state gap**：原子技能训练用的是 canonical start，而组合执行时下游技能必须从
  上游技能产生的 handoff state 启动；两者不匹配导致 transition 失败（§1、§4.1）。
- **PRTI = Pose Robust Task Initialization**，一句话定义（§4.2）：

> "an atomic post-training strategy that broadens the start-state coverage of each skill **without using
> composed demonstrations**."

### 2.2 输入 / 输出 / 改的是什么

| 问题 | 论文回答 | 位置 |
| --- | --- | --- |
| 输入 | 已有的**成功原子示范**（object poses、end-effector poses、contact configurations 的"late segments"） | §4.2 |
| 输出 | 一个**后训练过的原子策略**（同一 backbone、同一 observation/instruction/action 接口） | App. D |
| 改的变量 | **训练数据的初始状态分布**（不是推理时的机器人/物体状态） | §4.2、Eq. (7) |
| 是否依赖下游原子策略 | 是——它就是给原子策略做后训练 | §4.2 |
| 是否依赖专家数据 | 是——"initial states are sampled only from **pre-existing successful atomic demonstrations**" | §4.2 |
| 是否需要额外训练 | **是**，这是本方法的全部内容 | App. D |
| 是否用优化器/搜索/规划器 | 训练用优化器；**推理期不用规划器改状态** | §4.2、App. D |
| 是否在线状态估计 | **否** | §4.2 |

### 2.3 算法（论文给出的全部细节）

1. 从**成功原子轨迹的末段**构造辅助池 **S**（含物体位姿、末端位姿、接触构型）。
2. 对每个目标技能 `z_i`，取**任务可行子集** `S_i ⊆ S`（从这些状态出发 `z_i` 仍可执行）。
3. 仿真里由一个 **data engine** "restarts single skill trajectories from states sampled from `S_i`"；
   真机上则通过扰动物体位姿 / 机器人接近位姿 / fixture 状态补采单技能示范。
4. **训练混合比例 1:1**（canonical 轨迹 : PRTI 轨迹）。
5. 指令始终只给目标原子指令 `z_i`，**不越出 atomic-only 边界**。
6. 目标函数 **Eq. (7)**：
   `min_θ E_{i∼p(Z), x0∼m_i^α}[ L_atomic(θ; x0, z_i) ]`，
   其中 `m_i^α` 以非规范起始比例 `α` 混合 canonical 起始分布 `p_i^atom` 与可行辅助分布 `q̃_i`。

### 2.4 训练超参（App. D）

| 项 | 值 | 是否明确 |
| --- | --- | --- |
| 基座 | **π0.5 Robotwin checkpoint**（"initialized from an atomic skill checkpoint trained on the same task distribution"） | ✅ |
| 数据 | "two atomic data sources" 的混合，约 **10K episodes / ~2M frames / 数百条 atomic prompt** | ✅ 规模；❌ **两个 source 身份未公开** |
| 观测 | 3 路 RGB（1 external + 2 wrist），resize 224×224，+ proprio | ✅ |
| 参数更新 | **全参数**微调 | ✅ |
| 算力 | **4 accelerators** | ✅ |
| 步数 / batch | **50K steps / global batch 256** | ✅ |
| 优化器 | AdamW、cosine + warmup、EMA | ✅（**lr / warmup 步数 / EMA decay 未给**） |

### 2.5 实验协议（Table 2）

- 设定：**oracle HSE**（benchmark 提供 subtask queue 与 handoff cue），每任务 **20 episodes**（Table 2 caption）。
- 对照：**Base**（原子策略）、**Random**（非结构化初始状态扰动）、**Reset**（只把机器人复位，物体/接触保持）。
- 结果（19 任务平均，ordered success）：Base **2.63%**、Random **4.21%**、Reset **9.47%**、**PRTI 18.16%**；
  `Conv1→2`：7.52 / 12.50 / 29.75 / **39.88**。
- 真实机器人（Table 3）：13 个组合任务、5 次 rollout，Oracle-HSE 0.75 → **+PRTI 0.80**。

### 2.6 论文未给、但复现必需的信息（`UNVERIFIED`）

| # | 缺什么 | 影响 |
| --- | --- | --- |
| 1 | **data engine 的具体算法**：取示范的哪一段（"late segments" 的界定）、如何把物体/机器人恢复到该帧、接触状态如何重建、重采样失败判据 | **这是方法核心**；没有它只能自创一套 |
| 2 | `S_i` 的可行性判定流程（用专家 planner？重放？） | 决定数据质量 |
| 3 | `α` 的具体取值（"1:1" 对应 α=0.5，但未明说） | 影响复现一致性 |
| 4 | 两个 atomic data source 的身份 | 无法构造同分布数据 |
| 5 | lr / warmup / EMA decay | 训练复现 |
| 6 | π0.5 Robotwin atomic checkpoint 的下载地址 | **硬阻断** |

---

## 3. Official Code Mapping

### 3.1 论文步骤 → 源码（逐项）

| 论文步骤 | 官方代码位置 | 状态 |
| --- | --- | --- |
| 构造辅助池 S（成功原子轨迹末段） | **无** | ❌ NOT IMPLEMENTED |
| 任务可行子集 `S_i` | **无** | ❌ |
| 仿真 data engine 从 `S_i` 重启单技能轨迹 | 只有底层"从终态恢复"原语（见 3.2），**无入口、无脚本、默认关闭、且缺演示数据** | ⚠️ 原语存在，方法未实现 |
| 1:1 混合训练 | **无**（无训练代码） | ❌ |
| Eq. (7) 目标 | **无** | ❌ |
| 50K steps / 4 卡 / AdamW / cosine / EMA | **无** | ❌ |
| Table 2 的 oracle-HSE 评测 | ✅ 完整实现（`handoff_eval/` + `script/eval_policy.py`） | ✅ |
| Random / Reset 对照 | **无**（Reset 需要"只复位机器人"的执行期干预，代码里没有该模式） | ❌ |

**判定：官方代码没有实现论文的 PRTI，只实现了它用来评测的 HSE harness。**

### 3.2 最接近 PRTI 的代码：`terminal_state_init` / `robot_warmup`

`envs/_base_task.py` 里有一套"从 donor 终态恢复"的原语，看起来像 data engine 的残留：

| 位置 | 内容 |
| --- | --- |
| `_base_task.py:54` | `self.terminal_state_init_cfg = kwags.get('terminal_state_init', {'enabled': False})` |
| `_base_task.py:53` | `self.robot_warmup_cfg = kwags.get('robot_warmup', {'enabled': False})` |
| `_base_task.py:609-614` | `_load_terminal_state_bank(bank_path)`：读 JSONL 的"终态 bank" |
| `_base_task.py:619-620` | `_infer_task_start_gripper_targets()`：从 `ROOT_PATH/data/<task>/<task>_v/data/episode*.hdf5` 读示范 |
| `_base_task.py:728-778` | `run_terminal_state_init()`：按候选恢复场景、投影到相机、做碰撞检查 |
| `_base_task.py:762` | `raise ValueError('terminal_state_init_meta is required during **replay collection**')` |

但：

1. **默认关闭**：`task_config/robocombine_eval.yml:36-39` → `robot_warmup.enabled: false`、`terminal_state_init.enabled: false`；
2. **没有任何公开入口**：`git grep -n "terminal_state_init\|robot_warmup" -- script handoff_eval` = **0 命中**
   —— `eval_policy.py` / `run_split.py` 都没有 CLI 参数能打开它；
3. **依赖不存在的数据**：需要 `data/<task>/<task>_v/data/episode*.hdf5`（RoboTwin 原子示范布局），
   仓库里**没有 `data/` 目录**；
4. 它做的是**执行期**"把机器人/场景恢复到某个终态"，既不是数据生成，也没有接到训练。

**因此不能因为"函数名叫 terminal_state_init"就认定 PRTI 已实现。**

### 3.3 运行入口清单（公开）

| 目的 | 命令 |
| --- | --- |
| 评测入口 | `handoff_eval/runner/run_split.py` → `script/eval_policy.py`（仅此一个脚本） |
| 训练入口 | **不存在** |
| 数据生成入口 | **不存在** |

---

## 4. Dependency and Environment Audit

服务器：`222.29.51.96`（本次只查询，未启动任何任务）。

| 项 | 值 |
| --- | --- |
| OS / kernel | CentOS Linux 7 (Core) / 3.10.0-1160.el7.x86_64 |
| CPU / RAM | 80 核 / 251 GB |
| GPU | **5 × NVIDIA A40 46,068 MiB**，驱动 550.120 |
| CUDA toolkit | **未安装**（`nvcc` 不在 PATH；PyTorch 自带 cu121 运行时） |
| Motus 运行时 | Python **3.10.21**，torch **2.4.1+cu121**（`envs/motus`） |
| pi05 运行时 | **不存在**（`/scratch/lijh/*pi05*`、`*openpi*` 均无） |
| RoboTwin assets | `third_party/RoboCombine/assets` **16 GB**（embodiments / objects / background_texture 等） |
| 磁盘 | `/scratch` 15 TB，**剩余 154 GB（99% 已用）** |
| 本地权重 | Motus_robotwin2 15 GB、Wan2.2-TI2V-5B 14 GB、Qwen3-VL-2B 4 GB |
| PRTI 相关依赖 | 无（无 openpi 训练依赖、无 pi05 env） |

**结论**：环境足以跑 Motus 评测（B0 已证明），但**不足以跑 PRTI**：
既没有 pi05 运行时，也没有训练所需的依赖栈。

---

## 5. Checkpoint Audit

| 权重 | 官方地址 | 公开 | 本地 | 与论文关系 |
| --- | --- | --- | --- | --- |
| **Motus_robotwin2**（B0 用） | `motus-robotics/Motus_robotwin2` | ✅ | ✅ 15 GB，sha256 `70bc1741…` | 论文 Table 1 的一个 policy；**不是** PRTI 基座 |
| **π0.5 base** | `lerobot/pi05_base` | ✅ | ❌ | π0.5 通用基座，非 RoboTwin 微调版 |
| **π0.5 RoboTwin atomic**（PRTI 起点） | 未公开 | ❌ | ❌ | **PRTI 的必要前提** |
| **PRTI 后训练权重** | 未公开 | ❌ | ❌ | 复现 Table 2 的必要前提 |
| Wan / Qwen3-VL | 公开 | ✅ | ✅ | Motus 的组件 |

- HF `AutoLab-SJTU` 名下模型：CasaMeastro、SurroundNEXO、GSR —— **与 RoboCombine/PRTI 无关**。
- HF 搜索 `PRTI` / `RoboCombine` 均**无相关权重**。

---

## 6. Dataset Audit

| 资源 | 状态 | 说明 |
| --- | --- | --- |
| PRTI 训练数据（~10K 单技能 episodes、~2M frames、两个 source） | **`NOT_PUBLIC`** | 论文 App. D 只给规模，不给来源/下载 |
| RoboCombine HF 数据集 `AutoLab-SJTU/RoboCombine` | `PUBLIC_AND_AVAILABLE` | 950 episodes（19 任务 × 50）、285,806 frames；是**评测用组合 episode**，不是原子训练数据 |
| 其中 `RoboCombine_data-0.1.0.tar.gz`（13.1 GB） | `PUBLIC_BUT_NOT_DOWNLOADED` | "optional HDF5 trajectories, scene metadata, seeds, and MP4 previews" |
| `RoboCombine_eval_repo-0.1.0.tar.gz`（226 KB） | `PUBLIC_AND_AVAILABLE` | 评测仓库副本 |
| 数据集 README 明示 | — | "It does not contain private logs, **model checkpoints**, or local filesystem paths." |
| 仓库内 `data/<task>/<task>_v/data/episode*.hdf5` | **缺失** | `terminal_state_init` 的数据依赖，仓库不带 |

**结论**：公开数据可以支撑**评测**，不能支撑 **PRTI 的原子后训练**。

---

## 7. Simulation Asset Audit

| 资产 | 状态 | 说明 |
| --- | --- | --- |
| RoboTwin assets（16 GB） | ✅ 本地已有 | B0 已用其跑完 720 个有效 episode |
| 场景 / 物体 / 机器人 / 相机配置 | ✅ | `assets/` + `task_config/robocombine_eval.yml` |
| 19 个组合任务定义 | ✅ | `handoff_eval/specs/robocombine.json` |
| 原子任务 env（`envs/*_2tasks.py`） | ✅ | 与官方 HEAD 内容一致（本地 13 个文件仅行尾差异，`git diff --numstat` = 0/0） |
| PRTI 数据引擎所需 HDF5 示范 | ❌ | 未发布 |

---

## 8. Protocol Comparison

| 维度 | 论文 Table 2（PRTI） | 论文 Table 1（Motus） | 我们的 B0 |
| --- | --- | --- | --- |
| 基座策略 | **π0.5 Robotwin atomic** | Motus | **Motus_robotwin2** |
| 训练 | 50K steps × 4 卡，1:1 混合 | 未涉及（评测） | 无（用公开权重） |
| 评测轨道 | oracle HSE | oracle / ordered / full | oracle + full |
| episodes | 20 / 任务 | 20 / 任务 | 20 / 任务（720 有效） |
| 指标 | `SR_ord`、`Conv1→2` | `SR_ord` | `SR_ord`（+ env 分开统计） |
| 参考数值 | Base 2.63 / Random 4.21 / Reset 9.47 / **PRTI 18.16** | Motus Oracle 19.7 | Motus Oracle **49.2**、Full **18.9** |

**关键点**：论文 Table 2 的 "Base 2.63%" 与 Table 1 的 "Motus Oracle 19.7%" 不是同一个基座。
PRTI 的收益是**在 π0.5 这个弱基座上**测得的（2.63 → 18.16）。
我们的 B0 基座（Motus）已经 49.2%，**不能假设 PRTI 在同一基座上还能带来同样增益**，
也不能把两个数字放在同一张表里比较。

---

## 9. Relation to Previous Experiments

我们此前做过（`docs/00`、`docs/09`、`docs/11`）：

| 历史工作 | 与 PRTI 的关系 |
| --- | --- |
| B90 训练起点提取、A90/B90 初态对照（`docs/00`） | **同源问题**（start state 决定下游可执行性），但方法是**执行期**从训练初态启动 |
| 关节空间状态连接 / 物理运动规划（`docs/00`） | 执行期把机器人搬到某个构型；PRTI 是**训练期**改变策略见过的初始分布 |
| A/B/C 状态对照、物体场景对齐、末端-物体相对几何 | 执行期状态构造；PRTI 不需要这些机制，它需要的是**数据引擎** |
| 严格物理接触评价、冻结策略状态可执行性（`docs/09`） | 可作为 PRTI 的**下游评测**手段（判断"从该状态是否可执行"），但不能替代 PRTI 训练 |
| Handoff state gap 证据（`docs/11`） | 与论文 §4.1 的诊断**同向**，可作为 PRTI 动机的独立佐证 |
| 事件语义 trace（`docs/28`） | 评测期诊断工具，可复用 |

**结论**：

1. PRTI **没有**覆盖我们此前研究的机制，两者作用在不同阶段（训练期 vs 执行期）；
2. 我们的"物理连接"更接近论文的 **Reset 对照**（而且是更强版本：连物体一起搬），
   **不能**作为 PRTI 的复现，只能作为对照；
3. 我们的历史代码（env / trace / 评测 harness / 统计）**可以复用**；
4. 历史实验**不能**作为 PRTI 的复现结果。

---

## 10. Reproduction Feasibility

| 等级 | 定义 | 我们能否达到 | 阻断因素 |
| --- | --- | --- | --- |
| Level 1 | 读懂论文与代码 | ✅ **已达到** | — |
| Level 2 | 跑官方 PRTI **推理** | ❌ | 无 PRTI 权重；无 π0.5 RoboTwin atomic 权重；无 pi05 运行时 |
| Level 3 | 按论文协议**评测** | ❌ | 无 PRTI 权重（harness 本身已有） |
| Level 4 | 训练 + 推理 + 评测全复现 | ❌ | 无训练代码、无训练数据、无基座权重、算力不足（论文 4 卡 50K steps） |

**当前等级：Level 1。**

---

## 11. Minimal Experiment Plan（设计，**未执行**）

> 因 Level 2 未达成，本计划**不启动**。预注册文件 `docs/31` 标记 `NOT_READY`。

**若资源到位**，最小验证（与任务书 §9 对齐）：

| 组 | 方法 | 需要的权重 |
| --- | --- | --- |
| B0 | No Handoff Intervention（= 我们已冻结的 Motus oracle/full） | 已有 |
| B1 | 官方 PRTI | PRTI 权重（不存在） |
| B2 | 官方 Oracle HSE | 已有（= B0 的 oracle 轨道） |
| 可选 | Random / Reset 对照 | 需要执行期干预实现（官方未提供） |

- 任务：2 个组合任务（建议 `bakery_close`（有成功案例）与 `room_comfort`（ordered≫env））。
- 样本：20 episodes / 任务（与论文一致），固定 seed，独立目录，保留全部失败。
- 指标：`SR_ord`、stage success、`Conv1→2`、handoff 到达率、规划成功率、碰撞数、步数、推理时间、额外成本。
- 统计：原始计数 + Wilson CI。

---

## 12. Risks and Blockers

| # | 风险/阻断 | 类型 | 可否自行解决 |
| --- | --- | --- | --- |
| 1 | 官方仓库**无 PRTI 实现**（0 命中） | 实现 | ❌ 需作者提供代码或详细算法 |
| 2 | **无 π0.5 RoboTwin atomic checkpoint** | 资源 | ❌ 需作者发布 |
| 3 | **无 ~10K 单技能训练数据** | 资源 | ❌ 需作者发布 |
| 4 | data engine 算法未描述（取哪一段、如何恢复接触、重采样判据） | 方法 | ❌ 需作者确认 |
| 5 | 训练超参不全（lr / warmup / EMA decay / 两个 data source） | 方法 | ❌ |
| 6 | 无 pi05 运行时、无 openpi 训练栈 | 环境 | ⚠️ 可搭，但无权重无意义 |
| 7 | 算力：论文 4 卡 × 50K steps；我们 5×A40 但 `/scratch` 仅剩 154 GB | 算力/存储 | ⚠️ 勉强，但需先有数据 |
| 8 | 基座不同（Motus 49.2% vs π0.5 base 2.63%），收益不可直接迁移 | 科学解释 | ⚠️ 需重新定义对照 |

---

## 13. Final Decision

### `BLOCKED`

PRTI 的**论文定义清楚、动机与我们的 handoff 诊断一致**，但：

- 官方代码**没有实现**它（只有评测 harness）；
- 论文没有公开 **PRTI 权重**，也没有公开 **π0.5 RoboTwin atomic 基座**；
- PRTI 的**核心数据引擎算法**与**训练数据**均未公开。

在这三条任意一条未解决前，任何"PRTI 复现"都只能是**自创的近似方法**，
不能称为官方方法复现。**因此不建议进入 PRTI 实现阶段。**

### Q1–Q10

| # | 问题 | 回答 |
| --- | --- | --- |
| Q1 | PRTI 在论文中做了什么？ | 用"成功原子轨迹末段的 handoff-like 初态"做 1:1 混合的原子**后训练**，扩大原子策略的起始状态覆盖；不改推理流程、不用组合示范 |
| Q2 | 官方代码是否完整实现？ | **没有**。仓库只有 HSE 评测；PRTI 相关字符串 0 命中；训练/数据引擎入口不存在 |
| Q3 | 是否具备全部资源？ | **不具备**：缺 PRTI 权重、π0.5 RoboTwin atomic 权重、10K 单技能数据、训练代码 |
| Q4 | 能否直接用当前冻结的原子策略？ | **不能**直接用于 PRTI 复现（PRTI 要改的是训练分布）；但可用于 B0/B2 对照 |
| Q5 | 是否需要额外训练或下载 checkpoint？ | **需要**：π0.5 RoboTwin atomic ckpt（不存在）+ PRTI 后训练（需 50K steps × 4 卡） |
| Q6 | 与我们此前的物理状态连接实验区别？ | 我们是**执行期**状态构造（更接近论文 Reset 对照）；PRTI 是**训练期**分布扩展，二者互补、不可互替 |
| Q7 | 能否在现有 5×A40 上跑？ | **评测可以**（B0 已跑）；**PRTI 训练不行**（缺数据/代码/权重；存储仅剩 154 GB） |
| Q8 | 最小复现需要多少 GPU 时间和 rollout？ | 若权重到位：评测 2 任务 × 20 eps ≈ 2–4 GPU·h；训练按论文 4 卡 × 50K steps，**远超**当前许可范围 |
| Q9 | PRTI 是否值得作为后续横评 baseline？ | **作为方法值得**（它是最直接针对 start state gap 的 baseline）；**作为可复现 baseline 目前不值得**（无权重、无代码） |
| Q10 | 下一步：继续 PRTI / 解决资源 / 转向 DeCo？ | **转向 DeCo**（B2），同时把 PRTI 标为 `BLOCKED_EXTERNAL_RESOURCE`，向作者索取权重与 data engine 说明后再重启 |

**本阶段到此停止，不启动任何训练或 rollout。**
