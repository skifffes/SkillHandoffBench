# 33 · DeCo 资源、协议与可迁移性审计（Phase B2 / Gate C–F）

日期：2026-11-14。配套：`docs/32_deco_method_code_audit.md`（方法与代码映射）。
本文件回答：**资源够不够、协议是什么、能否移植到 RoboCombine、F1/F2 怎么判。**

---

## 1. 资源完整性（Gate D）

### 1.1 模型

| 资源 | 状态 | 证据 |
| --- | --- | --- |
| RVT-2 原子 checkpoint（DeCoBench 训练） | **`NOT_LOCATED_IN_PUBLIC_SOURCES`** | 仓库 0 个权重文件；HF/GitHub Release 未发现 |
| 3DDA 原子 checkpoint（DeCoBench 训练） | **`NOT_LOCATED_IN_PUBLIC_SOURCES`** | 同上；README 只链接**原版 3DDA** 权重（`katefgroup/3d_diffuser_actor`，peract/calvin），非本方法产物 |
| ARP 原子 checkpoint（DeCoBench 训练） | **`NOT_LOCATED_IN_PUBLIC_SOURCES`** | 同上 |
| VLM（论文） | GPT-4o（**API，收费**） | 论文 §III-C |
| VLM（代码） | **Qwen2.5-VL-7B + LLaMA-Factory 微调**（HF 可下载基座） | `HIGH_LEVEL.md`、`src/high_level/vlm/*` |
| 训练配置/归一化统计 | 部分（baseline 自带），**无 DeCoBench 专用** | `baselines/*/README.md` |

> 说明：不是"作者肯定没发布"，而是**本次检索（GitHub tree、repo README、HF 搜索）未定位到**。

### 1.2 数据

| 资源 | 状态 | 说明 |
| --- | --- | --- |
| DeCoBench 原子示范（4 源任务） | **`NOT_LOCATED_IN_PUBLIC_SOURCES`** | 需用 `HiMan-Bench/robot-colosseum/collect_dataset_train_*.sh` **自行采集**（脚本在，但那是 RoboHiMan 任务集） |
| DeCoBench 组合评测集（12 任务 × 20） | **`NOT_LOCATED_IN_PUBLIC_SOURCES`** | 同上 |
| RLBench 任务定义（`.ttm`） | `PUBLIC_AND_AVAILABLE`（vendored） | 245 个 `.ttm`，含 open_drawer / close_drawer / put_in_opened_drawer / take_out_of_opened_drawer / box_in_cupboard / box_out_of_cupboard / broom_out_of_cupboard / sweep_to_dustpan / rubbish_in_dustpan / sweep_and_drop / retrieve_and_sweep |
| 采集成本 | 4 源任务 × 50 示范，CoppeliaSim 内脚本策略 | 未测；按 RLBench 常规，**单任务数十 episode 分钟级**，4 任务约 1–3 小时机时（估算） |

**关键点**：公开的是**代码 + RLBench 任务文件**，不是**数据**。
若坚持复现 DeCoBench，必须自己采 4×50 条示范并自行划定 12 个组合任务与 variation
——这已经不是"复现"，而是"按描述重建"。

### 1.3 仿真环境

| 项 | 论文/代码要求 | 我们当前 |
| --- | --- | --- |
| 仿真器 | **CoppeliaSim Edu V4.1.0**（Ubuntu 20.04 构建） | 需要容器（服务器是 **CentOS 7**） |
| PyRep / RLBench | 从 `baselines/RVT-Baseline/rvt/libs/` 安装 | 未安装 |
| Python | 3.11（`uv venv --python 3.11`） | 无 3.11 环境 |
| 依赖 | `uv pip install -r PyRep/RLBench` + robot-colosseum | 未安装 |
| 渲染 | 需 `xvfb-run` + OpenGL | A40 可用，但需 headless GL 配置 |

### 1.4 运行与成本

| 场景 | 需求 | 5×A40 可行性 |
| --- | --- | --- |
| 单次推理（RLBench + 3DDA/RVT） | 1 GPU + CoppeliaSim | 可行（需容器化环境） |
| VLM 推理 | 论文 GPT-4o API；代码 Qwen2.5-VL-7B（~16 GB） | 可行（A40 46 GB） |
| Chaining | 需点云 + cost map | **代码不存在** |
| 原子重训 | 论文 8×4090；每任务 50 demos | 5×A40 **算力接近 3×4090 等效**，但**无数据** |

**A40 vs 4090**：单卡 FP16 算力相近（~150 vs ~165 TFLOPS），A40 显存更大（46 vs 24 GB）。
5×A40 ≈ 3.1 张 4090 的等效吞吐。论文的 8×4090 训练预算在小数据量下对我们不是主要瓶颈。

---

## 2. 论文协议（Gate C）

### 2.1 DeCoBench

- **4 个源任务** → **10 个原子技能** → **12 个未见组合任务**：
  - Object Rearrangement with Drawer：2 个 4-cycle、5 个 6-cycle、2 个 10-cycle；
  - Object Rearrangement with Cupboard：exchange boxes（4-cycle）；
  - Rubbish Cleanup：sweep and drop（4-cycle）；
  - 跨域：transfer box（6-cycle）、retrieve and sweep（4-cycle）。
- 域：Drawer / Cupboard / Rubbish Cleanup。
- 任务定义源自 RLBench（论文明确 "heavily inspired by RLBench"）。

### 2.2 训练与评测规模

| 项 | 值 |
| --- | --- |
| 原子训练示范 | **50 / 原子任务** |
| 组合评测 | **20 test demonstrations / 任务** |
| seeds | **3 个随机种子** |
| 总 rollout（估算） | 12 × 20 × 3 = **720** 次/模型 |
| 硬件 | 8 × RTX 4090 |
| batch | RVT-2 24 / ARP 48 / 3DDA 8 |
| 观测 | 4 RGB-D；128×128（RVT-2/ARP）、256×256（3DDA） |
| goal pose 坐标系 | robot base frame |

### 2.3 "20 episodes × 3 seeds" 到底怎么组织（**必须澄清**）

论文原话（§V-A）："evaluated on compositional tasks (**20 test demonstrations per task**)…
All policies are evaluated with **three random seeds**"；Table I caption 又说
"3 seeds, with **20 test episodes per task**"。

两种可能：

1. **3 seeds × 20 个固定 test demo** = 每任务 60 次 rollout（seed 只控制策略采样/环境随机化）；
2. **3 seeds × 20 次随机初始状态** = 每任务 60 次，但初始化不同。

论文**没有说明** seed 具体控制什么（策略采样？物体初始位姿？物体材质的随机化？）。
→ 标 `UNVERIFIED`。**这与 RoboCombine 的"20 eps + base-seed 42 + 专家筛 seed"不是同一套规则，不能照搬。**

### 2.4 指标

- 主指标：**success rate**（任务成功率），原子 SR 与组合 SR **分开报告**。
- 与 RoboCombine 的 **`sr_ordered` 不等价**：RoboCombine 的 ordered 是"两子任务按序触发"，
  DeCo 的 success 是 RLBench 的 `task.success()`（终局条件）。**不可直接比较。**

---

## 3. 训练/测试泄漏审计

| 风险 | 是否存在 | 证据 |
| --- | --- | --- |
| DeCo 原子训练混入组合示范 | **否**（论文声明 atomic-only；Table III 专门做了 "6 Long training" 对照） | §III-B、Table III |
| RoboHiMan 的 **L4** 数据含组合示范 | **是**（`train_compositional_C`、`train_compositional_CP` 被软链接进 L4） | `INSTALL.md` 采集脚本 + `multi_level_data_rearrange.py` |
| 用 L4 训练再报"零样本" | **会构成泄漏** | 同上 |
| 用 `6 Long training` 模型与 DeCo 对比 | 论文已单列（Table III），**不能混入零样本组** | Table III |
| 我们在 RoboCombine 的 B0 是否泄漏 | 否——Motus 为公开权重，未在 RoboCombine 上训练 | `docs/14`、`docs/19` |

**结论**：若未来移植 DeCo 到 RoboCombine，**必须显式声明所用原子模型是否见过测试组合**；
用 L4 或多级数据训练的模型不能标注为"零样本原子基线"。

---

## 4. RoboCombine 可迁移性（Gate E，仅审计，不实现）

### 4.1 核心差异

| 维度 | 原版 DeCo | RoboCombine（我们的 B0） | 兼容性 |
| --- | --- | --- | --- |
| 仿真 | RLBench / CoppeliaSim 4.1.0 | RoboTwin 2.0（SAPIEN） | ❌ 不同引擎 |
| 低层模型 | RVT-2 / 3DDA / ARP | Motus（+π0.5 可选） | ❌ 接口不同 |
| 动作表示 | EEF 关键帧 + 离散夹爪（RLBench `MoveArmThenGripper`） | 连续 EEF delta + 夹爪（chunked） | ⚠️ 需适配 |
| 观测 | 4 RGB-D + 点云 | 3 RGB + proprio | ⚠️ 点云需自行生成 |
| Skill goal pose | 由示范关键帧给出，**显式用于完成判定** | **无 goal pose 概念**；技能完成 = 子任务谓词 | ❌ 缺关键机制 |
| Skill start pose | 由下一技能 goal 预测得到（chaining 输入） | **无** | ❌ |
| 技能切换 | goal-pose 位姿闭环 | 官方 `sequential` 子任务谓词 + HSE cue | ⚠️ 语义不同 |
| 物理连接 | VoxPoser cost map → chaining poses | 无（直接切换指令） | ❌ 缺模块 |
| 成功指标 | RLBench `success()` | `sr_ordered` + env success | ⚠️ 不等价 |
| 特权信息 | 点云、goal pose（来自示范） | 无 goal pose；有物体位姿（仿真） | ⚠️ |

**论文的"model-agnostic"是方法主张，不等于已证明与 Motus 兼容。**
从实际 contract 看：Motus 没有 goal pose 监督接口，RoboCombine 也没有"技能完成 = 到达目标位姿"的定义。

### 4.2 两条路线

| 路线 | 定义 | 可行性 |
| --- | --- | --- |
| **O：Original DeCo Reproduction** | DeCoBench + 原始低层模型 + 完整方法 | **BLOCKED**（代码缺 chaining；数据/权重缺失） |
| **C：Controlled RoboCombine Adaptation** | 固定 RoboCombine + Motus，研究"DeCo 的连接与调度机制"能否改善成功率 | `FEASIBLE_WITH_MAJOR_ADAPTATION`（需重写 goal-pose 判定与连接模块，属再实现） |

路线 C **不能**冒充路线 O；即使忠实复用算法，也属于跨平台再实现。

### 4.3 移植时必须显式消除的混杂变量

1. 是否用**同一个冻结 Motus**（B0 的 `Motus_robotwin2`）；
2. 是否引入**原子技能之外的训练数据**（若训练则不再是零样本）；
3. 是否读取**仿真 Oracle**（物体位姿/点云）；
4. VLM 是否**决定技能顺序**（RoboCombine 已给定顺序时，VLM 组件被架空）；
5. 是否**增加运动规划工具**（会改变动作预算）；
6. 是否**增加物理动作预算**（chaining 本身消耗步数）；
7. 是否使用**额外深度/物体位姿**；
8. 新增**计算/模型调用/执行时间**（成本必须同表报告）；
9. 与 B0 的**初始状态是否配对**（同 seed、同 scene）。

### 4.4 对 B4（Agent 负责交接与恢复）的能力分析

| 问题 | DeCo 已实现？ | 说明 |
| --- | --- | --- |
| 是否真正选择"下一技能的可执行启动状态" | **部分**（论文里是 cost map 生成 chaining poses；公开代码没有） | 论文层：是；代码层：否 |
| 还是只把末端移动到预测 start pose | 论文：不止；代码：**连这个都没有**（只有 home reset） | — |
| 是否检查对象/接触/夹爪完整交接状态 | **否** | 只检查夹爪开合/抓取集合做切换 |
| 是否具有在线失败恢复 | **否**（论文未描述；代码无） | `UNVERIFIED` |
| 失败归因（VLM / 连接 / 原子策略） | 论文有定性讨论；代码无分解日志 | 需自建 |

---

## 5. 复现门槛与预算

### 5.1 复现 DeCoBench 的硬门槛

| # | 门槛 | 现状 |
| --- | --- | --- |
| 1 | 官方 chaining 实现（cost map + chaining poses） | ❌ 不存在 |
| 2 | DeCoBench 任务划分 / variation / 评测脚本 | ❌ 不存在 |
| 3 | 4 源任务 × 50 示范（或官方示范数据） | ❌ 需自采 |
| 4 | RVT-2/3DDA/ARP 的 DeCoBench 训练权重 | ❌ 未定位 |
| 5 | GPT-4o 或等价 VLM（论文用 API） | ⚠️ 可用 Qwen 替代，但**不是同一方法** |
| 6 | CoppeliaSim 4.1.0 + PyRep/RLBench 环境 | ⚠️ 需容器化（CentOS 7） |

### 5.2 预算（估算，非实测）

| 项 | 估算 | 备注 |
| --- | --- | --- |
| 采集 4×50 示范 | 1–3 GPU·h（含 xvfb 渲染） | 需先有环境 |
| RVT-2 训练（10 原子 × 50） | 1–2 天 × 8×4090（论文配置） | 5×A40 约 2–4 天等效 |
| 3DDA / ARP 训练 | 各 1–3 天 | 同上 |
| 评测 12 × 20 × 3 | 数百 GPU·h（CoppeliaSim 渲染慢） | 未计 chaining 开销 |
| 磁盘 | 示范 + 渲染缓存 ≈ 数百 GB | 当前 `/scratch` **仅剩 154 GB** |
| API | GPT-4o 若用：数十美元级（估） | 论文未给 token 预算 |

**注**：以上仅为量级估计，**没有实测**；且第 1、2、3、4 项门槛未过，预算无意义。

---

## 6. Gate F 决策

### F1. ORIGINAL_DECO_REPRODUCTION

# `BLOCKED_MISSING_CODE`

主因：**DeCo 的第三个核心组件（空间感知 chaining / cost map）在公开代码中不存在**，
且执行循环把"技能完成"换成夹爪状态 + home 复位——与论文主张相反。
次因：DeCoBench 划分、示范数据、原子权重均未公开（`BLOCKED_MISSING_DATA` / `BLOCKED_MISSING_CHECKPOINT`）。

**最小补齐条件**：作者提供 chaining 模块（或算法级伪代码 + 超参）+ DeCoBench 划分 + 原子权重/示范。
**能否请求作者**：可以，且成本远低于自建。
**能否只复现部分组件**：可以，但只能叫"部分组件复现"，不能叫"DeCo 复现"；
其中 **VLM 调度**部分可跑（代码完整），**chaining** 部分无法复现。

### F2. ROBOCOMBINE_PORT_FEASIBILITY

# `FEASIBLE_WITH_MAJOR_ADAPTATION`

理由：RoboCombine 没有 goal-pose 概念、没有点云接口约定、Motus 是 chunk 动作，
DeCo 的完成判定与连接机制必须重写；这属于**再实现**，不是移植。
F2 可行**不代表**允许本轮开始适配（本轮只审计）。

---

## 7. 结论

1. **DeCo 原方法无法从公开材料复现**（代码缺一个核心组件，数据与权重缺失）。
2. 公开代码可以复现的是 **RoboHiMan 的分层评测**（Vanilla / Rule / VLM 三种设置），
   它**不是** DeCo，不能标成 DeCo 的复现结果。
3. 移植到 RoboCombine 在原理上可行，但需要重写完成判定与连接模块，属于新实现，
   必须与"路线 O"严格区分，并显式声明所有混杂变量（见 §4.3）。
