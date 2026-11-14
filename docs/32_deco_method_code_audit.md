# 32 · DeCo 方法与官方代码审计（Phase B2 / Gate A–B）

日期：2026-11-14。论文：**DeCo: Task Decomposition and Skill Composition for Zero-Shot
Generalization in Long-Horizon 3D Manipulation**（arXiv:2505.00527，v1 与 **v2** 均读）。
审计方式：只读。未训练、未 rollout、未下载权重/数据集、未调用任何 VLM API。

> **一句话结论：项目网站指向的 RoboHiMan fork 只改了 README；DeCo 的三个核心组件里，
> VLM 规划被换成了微调 Qwen2.5-VL，chaining 模块根本不存在，执行循环用的是
> "夹爪状态变化触发切技能 + 回 home 位姿"，这与论文的 goal-pose 监控 + 空间感知连接不是同一个方法。**

---

## 1. 论文方法还原（Gate A）

### 1.1 三个核心组件（论文 §III）

论文原文（v2，§III 开头）：

> "DeCo includes three key components: 1) Physical Interaction-based Task Decomposition and
> Skill Learning. 2) VLM-Guided Planning and Skill Scheduling. 3) Spatially-Aware Skill Chaining."

| 组件 | 论文要求 | 依据 |
| --- | --- | --- |
| ① 任务分解 + 原子技能学习 | 用**抓取交互周期**分解原始示范；`p^full`（完整交互）与 `p^half`（半交互）两种粒度；关键帧发现；原子指令库 `L^a`；训练多任务 IL 模型 | §III-B |
| ② VLM 规划与调度 | **GPT-4o** 接收任务指令 + RGB 图像 + 原子指令库，输出下一步技能；**goal-pose 闭环监控**判断技能完成 | §III-C |
| ③ 空间感知技能连接 | 当前 goal pose + 预测的下一技能 start pose + 场景点云 → **改编自 VoxPoser 的 cost map** → 无碰撞 chaining poses | §III-D |

### 1.2 关键细节（逐项）

**A1 原子数据与训练**

- 分解依据：**完整物理交互 `p^full`**（"each aligned with a full gripper interaction"）；另实现 `p^half` 变体用于消融。
- 关键帧：`keyframe discovery method [43]`，依据**夹爪状态切换或关节速度近零**。
- goal pose：每条示范以 `p^full` 结束，末端位姿即该原子技能的 goal pose（论文："Each demonstration
  concludes with a full physical interaction…and the end-effector…"）。
- 指令：每个原子任务 `T_i^a` 配一条语言指令 `ℓ_i^a`，构成指令库 `L^a`。
- 训练目标：`θ* = argmin E[L_MT-IL(π^a_θ(o, ℓ_i^a), a)]`。
- 训练数据规模：**每个原子任务 50 条示范**（§V-A、Table I caption）。
- 是否存在组合示范进入原子训练集：**没有**（论文明确 atomic-only；Table III 另设"6 Long training"对照）。
- 是否要求重新训练原子策略：**是**——DeCo 本身就是"分解 + 重训"的框架（`M+DeCo`）。
- 纯推理期 DeCo vs 完整 DeCo：论文没有"纯推理期"版本；只有 `p^full` / `p^half` 两种分解粒度。

**A2 VLM 规划**

- 模型：**GPT-4o**（§III-C）。
- 输入：novel task 指令、**观测 RGB 图像**、**预建原子指令库**。
- 输出：高层计划（技能序列）。
- 何时重新调用：论文未明确给出频率（`UNVERIFIED`）；只在 §III-C 说"invokes the VLM"。
- 完成判定：**"continuously monitors the robot pose and checks it against the goal pose of the
  current skill"**（§III-C）——即**位姿闭环**。
- 失败处理/重规划：论文未描述（`UNVERIFIED`）。
- 真实 prompt：项目网站 `docs/static/prompts/{full,half}/template.txt`（66/68 行，本审计已取样）。

**A3 空间感知连接（重点）**

- 输入：**当前 goal pose**、**预测的下一技能 start pose**、**场景点云**。
- 方法：**cost map 模块改编自 VoxPoser**；生成"collision-free chaining poses"。
- 消融：`Chaining Poses Num = 0` 关闭该模块后性能显著下降（§V-D）。
- 论文明确说：**不用常规全局运动规划器**（"does not rely on a conventional global motion planner;
  instead, it employs a short-horizon, spatially constrained motion-bridging module"）。
- RRT：**论文正文没有把 RRT 作为方法组件**（全文 `RRT` 仅出现在参考文献与常规表述中）。

> 因此"cost map + RRT"这个组合**不能**直接当成论文方法：论文是 **VoxPoser 风格 cost map 生成
> chaining poses**，不是"用 RRT 做全局规划"。这一点在代码审计里也得到印证（见 §3.3）。

### 1.3 实验协议（Gate C 前置）

| 项 | 论文值 | 出处 |
| --- | --- | --- |
| Benchmark | DeCoBench：4 个源任务 → **10 个原子技能** → **12 个未见组合任务**（3 域 + 2 跨域） | §IV、Fig. 4 |
| 原子示范 | **50 / 原子任务** | §V-A |
| 组合评测 | **20 test demonstrations / 组合任务** | §V-A |
| seeds | **3 个随机种子** | §V-A |
| 硬件 | **8 × RTX 4090** | §V-A（v2 才有；v1 未写 GPU 型号） |
| batch | RVT-2 24 / ARP 48 / 3DDA 8 | §V-A |
| 观测 | 4 路 RGB-D（front / left shoulder / right shoulder / wrist） | §V-A |
| 图像分辨率 | RVT-2、ARP 128×128；3DDA 256×256 | §V-A |
| goal pose 坐标系 | **robot base frame** | §V-A |
| 主要结果 | RVT-2 **0.00 → 66.67**；3DDA 0.00 → 21.53；ARP 0.14 → 58.06（12 任务） | §V-B、Table II |
| 真实机器人 | Franka + D435i，6 原子任务 → 9 组合任务，各 10 次 | §V-A、Table IV |

**v1 vs v2 差异**：核心数字一致（66.67 / 21.53 / 58.06、50 demos、20 test、3 seeds）；
v2 补了 GPU 型号（8×4090）；两版表格编号不同（v1 的 Table 1 是 12 个长时序任务，v2 的 Table I 是 10 个原子任务）。
逐句 diff 未做 → 该比对标 `PARTIAL`。

---

## 2. 代码来源与完整性（Gate B）

### 2.1 实际访问的版本（审计时刻）

| 对象 | 值 |
| --- | --- |
| 项目网站 | `https://deco226.github.io/`（HTTP 200） |
| 网站 Code 链接 | `https://github.com/chenzixuan99/RoboHiMan` |
| 该仓库性质 | **fork = True**，parent = `chenyt31/RoboHiMan` |
| fork HEAD | `d18332b2a78dc5350ffcac8157bd166173e7321f`（2025-12-25） |
| upstream HEAD | `33f71d30d9a100a83725ff00dfcc27374d5ce810`（2025-10-16，"Initial clean commit"） |
| fork 相对 upstream | **ahead_by = 2，behind_by = 0，改动文件 = 1（README.md，+12/−1）** |
| 仓库规模 | 13,017 个 entry；894 个 .py；245 个 .ttm；**0 个权重文件**（.pth/.pt/.ckpt/.safetensors） |

**fork 的两个提交**：

1. `7c8da843ac` "Update README with DeCo support information"
   —— 在 README 顶部加一句 "This codebase supports the reproduction of **DeCo**"。
2. `d18332b2a7` "Update README with citation details"。

→ **fork 没有新增任何代码。** DeCo 的"官方代码"实质就是 upstream RoboHiMan。

### 2.2 RoboHiMan 是什么（重要）

- RoboHiMan 是**另一篇论文**（arXiv:2510.13149）的代码库，主题是"**分层评测范式** + HiMan-Bench"
  （atomic / compositional tasks、multi-level 数据、Vanilla / Rule-based / VLM-based 三种设置）。
- 它的 README 引用了 `@article{chen2025deco}`（作者重叠），并在致谢里列了 DeCo 链接。
- 它自带 4 个 baseline 的**完整 vendored 副本**（RVT、3D-Diffuser-Actor、OpenPi、OpenPi05），
  以及 **RLBench/PyRep 的完整副本**（这是仓库 680 MB 的主要来源）。

**结论**：这是"同一作者组的另一个项目的代码库，被声明可用于复现 DeCo"，
而不是"DeCo 论文的官方实现仓库"。二者不能等同。

### 2.3 三个核心组件的调用链

#### ① 任务分解 / 原子数据

| 位置 | 内容 | 判定 |
| --- | --- | --- |
| `src/utils/data_engine.py`（235 行） | RVT 风格数据集构建：`keypoint_discovery`、`gripper_change`、`touch_change`、`goal_keyframe`、生成 `action_ls`/`subgoal_action_ls` | `PARTIAL_IMPLEMENTATION`（有关键帧/目标帧，但**没有**按 `p^full`/`p^half` 把长示范切成原子任务数据集） |
| `src/data_preprocessing/multi_level_data_rearrange.py`（51 行） | 把 L1–L4 四个目录的 episode **软链接**合并 | `MISMATCH`（RoboHiMan 的数据分级，不是 DeCo 分解） |
| 数据采集脚本（`HiMan-Bench/robot-colosseum/collect_dataset_train_{A,AP,C,CP}.sh`） | 用脚本策略采集 RoboHiMan 数据 | `EXTERNAL_DEPENDENCY`（不是 DeCoBench 的 4 源任务） |

#### ② VLM 规划与调度

| 位置 | 内容 | 判定 |
| --- | --- | --- |
| `src/high_level/vlm/agent.py`（40 行） | `MultiModalAgent.run()` → `QwenVLRunner.infer()`；模板名 `f"{task_name}_{runner.mode}.jinja2"` | **`MISMATCH`**：论文用 **GPT-4o**，代码用**微调 Qwen2.5-VL** |
| `src/high_level/vlm/models/qwen_vl_runner.py` | 本地 Qwen2.5-VL 推理 | 同上 |
| `src/high_level/prompts/qwen_vl/next_sub_task_w_history_api.jinja2`（19 行） | 输入 `image_paths` + `task_description` + `pre_sub_tasks`，输出 `<reasoning>…</reasoning><sub_task>…</sub_task>` | 与论文网站 `template.txt` **不是同一套 prompt** |
| `HIGH_LEVEL.md` | 用 **LLaMA-Factory** 训练 Qwen2.5-VL（L1 数据 + CoT 预处理 + full/LoRA） | **训练出来的 planner**，论文没有这一训练步骤 |
| `src/high_level/eval.py`（255 行） | **离线**逐帧预测"下一个子任务"，与 GT 字符串比对算准确率 | `MISMATCH`：这不是闭环机器人执行 |

#### ③ 空间感知技能连接 —— **不存在**

搜索证据（全部只读）：

| 搜索 | 结果 |
| --- | --- |
| 全仓路径名含 `chain/costmap/cost_map/voxposer/rrt/deco/skill/keyframe` | 4 个命中，**都不是**实现：`ycb_028_skillet_lid.ttm`、`ycb_059_chain.ttm`（资产）、`baselines/RVT-Baseline/rvt/utils/rlbench_planning.py`（RVT 自带）、`src/high_level/data_preprocessing/planning_sft_data.py`（VLM SFT 数据） |
| 对 10 个核心源文件（`agent.py`、`eval.py`、`data_engine.py`、`env_engine.py`、`env_utils.py`、`vlm_utils.py`、`dataset_utils.py`、`multi_level_data_rearrange.py`、`planning_sft_data.py`、`prompt_manager.py`）做内容 grep：`voxposer|cost.?map|chaining|rrt|motion.?bridge|planner` | **0 命中** |
| 仓库权重文件 | **0** |

→ **`PAPER_ONLY`：DeCo 的第三个核心组件在公开代码中不存在。**

### 2.4 真正的执行循环（`eval_mode` 三种模式）

`baselines/3d-Diffuser-Actor-Baseline/online_evaluation_rlbench/evaluate_policy_himan.py`（267 行）
→ `utils/utils_with_rlbench.py:697-860`（`_evaluate_task_on_one_variation`）：

```python
if eval_mode == "vanilla":      instruction = instruction_vanilla
elif eval_mode == "half":       instruction = instruction_oracle_half[instr_index]
elif eval_mode == "vlm":        instruction = <Qwen2.5-VL 预测的下一子任务>
...
# 切技能：靠夹爪/抓取集合变化，不是 goal pose
if (cur_grasped_objects_len != prev_grasped_objects_len or
        abs(cur_gripper_state - prev_gripper_state) > 1e-6):
    instr_index = (instr_index + 1) % len(instruction_oracle_half)
    # reset when grasped changed and gripper open
    if abs(obs.gripper_open - 1.000) < 1e-9:
        obs, _, _ = self.env._task.step(home_pose)   # ← 机械臂回 home
```

三个关键事实：

1. **切技能的依据是夹爪状态/抓取集合变化**，不是论文说的"机器人位姿 vs goal pose"。
2. **夹爪张开时把机械臂复位到 home pose** —— 这恰好是论文用来做**对照**的 "Reset" 行为
   （"returns only the robot to its canonical pose between subtasks"）。
3. 动作执行走 RLBench `Mover`（`EndEffectorPoseViaPlanning`，内部 RRT-based IK），
   这是 **`GENERIC_MOTION_PLANNER`**，**不是** `DECO_SPATIALLY_AWARE_CHAINING`。

### 2.5 模块完整性总表（Gate A4）

| 模块 | 论文要求 | 公开源码位置 | 可执行入口 | 完整性 | 缺失项 |
| --- | --- | --- | --- | --- | --- |
| 原子数据分解 | 按 `p^full`/`p^half` 切分 + 关键帧 + goal pose | `src/utils/data_engine.py` | 数据集构建脚本 | `PARTIAL_IMPLEMENTATION` | 没有"切分"逻辑；无 `p^half` 数据集构建 |
| 原子策略训练 | RVT-2 / 3DDA / ARP 各训 50 demos/任务 | `baselines/*`（vendored 原仓库） | 各 baseline 训练脚本 | `EXTERNAL_DEPENDENCY` | 无 DeCoBench 专用配置/数据 |
| VLM 技能检索 | GPT-4o + 原子库 + RGB | `src/high_level/*` | `eval.py`（离线）/ `evaluate_policy_himan.py`（在线） | `MISMATCH` | 模型换成 Qwen2.5-VL；prompt 不同 |
| 动态调度 | 每步/每技能调用 VLM，按完成度推进 | `utils_with_rlbench.py:759-790` | `--eval_mode vlm` | `PARTIAL_IMPLEMENTATION` | 推进依据是夹爪变化，不是 goal pose |
| Goal-pose 判断 | 位姿闭环监控 | **无** | — | `PAPER_ONLY` | 无 goal pose 表、无位姿比较 |
| 空间感知 cost map | VoxPoser 改编 | **无** | — | `PAPER_ONLY` | 整个模块缺失 |
| RRT 连接 | chaining poses 生成 | **无**（只有 RLBench Mover 执行策略动作） | — | `PAPER_ONLY` | 无 chaining pose 生成器 |
| 任务评测 | DeCoBench 12 组合 | 无 DeCoBench runner；有 HiMan-Bench runner | `evaluate_policy_himan.py` | `MISMATCH` | 任务集与指标不同 |

---

## 3. 源码证据索引

| 证据 | 路径 / 行号 |
| --- | --- |
| fork 关系与 2 个提交 | GitHub compare `33f71d30…...d18332b2…`：ahead 2，files=1（README +12/−1） |
| fork README 的 DeCo 声明 | `README.md` 第 1 行（fork 版） |
| 仓库规模/权重 | GitHub tree API：13,017 entries，0 个权重文件 |
| VLM agent | `src/high_level/vlm/agent.py:1-40` |
| VLM 训练说明 | `HIGH_LEVEL.md`（LLaMA-Factory、Qwen2.5-VL、L1 数据 + CoT） |
| 离线 planner 评测 | `src/high_level/eval.py:117-255` |
| 在线评测入口 | `baselines/3d-Diffuser-Actor-Baseline/online_evaluation_rlbench/evaluate_policy_himan.py:1-267` |
| 执行循环 / 切换 / home reset | `baselines/3d-Diffuser-Actor-Baseline/utils/utils_with_rlbench.py:697-860`（切换在 845-855） |
| 关键帧与 goal 帧 | `src/utils/data_engine.py:52-105` |
| 多级数据（软链接） | `src/data_preprocessing/multi_level_data_rearrange.py:24-51` |
| 环境安装（CoppeliaSim 4.1.0 / PyRep / RLBench） | `INSTALL.md:1-98` |
| 论文 prompt（网站） | `DeCo226.github.io:docs/static/prompts/{full,half}/template.txt` |

---

## 4. 论文 vs 公开代码：逐项差异

| # | 论文 | 公开代码 | 类型 |
| --- | --- | --- | --- |
| 1 | GPT-4o（零样本 prompt） | 微调 Qwen2.5-VL（LLaMA-Factory） | **模型替换** |
| 2 | 用 goal pose 判断技能完成 | 用夹爪/抓取变化判断 | **机制替换** |
| 3 | 技能间做空间感知 chaining（cost map） | 夹爪张开时回 home pose | **对照≠方法** |
| 4 | 不复位机器人，直接承接 handoff 状态 | `step(home_pose)` 复位 | **与论文核心主张相反** |
| 5 | DeCoBench 12 任务 | HiMan-Bench 任务 | **任务集不同** |
| 6 | 4 路 RGB-D，128/256 | 同一套相机配置 | 一致 |
| 7 | 50 demos/原子任务 | 数据需自行采集（脚本在） | 数据缺失 |
| 8 | 8×4090 | 未声明 | `UNVERIFIED` |

---

## 5. Q1–Q10

| # | 回答 |
| --- | --- |
| **Q1** | 训练期：按抓取交互周期分解示范（`p^full`/`p^half`）+ 重训多任务 IL 模型（50 demos/任务）。推理期：GPT-4o 生成技能序列 → 每技能执行到 goal pose（位姿闭环）→ VoxPoser 风格 cost map 生成 chaining poses 连接下一技能起点。 |
| **Q2** | **没有。** 只有 VLM 调度（换成微调 Qwen）和一个 baseline 执行循环；**chaining/cost map 完全缺失**，goal-pose 判断缺失，切换靠夹爪状态 + 回 home 复位。 |
| **Q3** | 网站指向 `chenzixuan99/RoboHiMan`，它是 `chenyt31/RoboHiMan` 的 fork，**只改了 README（+12/−1）**。RoboHiMan 本身是另一篇论文（2510.13149）的分层评测代码库，作者组重叠；**不是 DeCo 的官方实现**。 |
| **Q4** | **不齐全。** DeCoBench 的 10 原子/12 组合任务定义在 vendored RLBench 的 `.ttm` 里有同名任务（open_drawer、put_in_opened_drawer、box_in_cupboard、sweep_to_dustpan、rubbish_in_dustpan、retrieve_and_sweep 等），但没有 DeCoBench 的划分、variation、评测脚本与示范数据。 |
| **Q5** | **没有。** 仓库 0 个权重文件；未找到 RVT-2/3DDA/ARP 的 **DeCoBench 训练**权重。3DDA README 只链接到原版 3DDA 的 HF 权重（`katefgroup/3d_diffuser_actor`），不是本方法产物。 |
| **Q6** | **不能。** VLM 调度可以跑（Qwen 本地推理），但 chaining 没有实现；执行循环里没有 cost map / chaining pose / goal-pose 判断。 |
| **Q7** | 若按论文：4 源任务 × 50 示范采集 + 10 原子训练（3 模型）+ 12×20×3 评测 + 8×4090 训练预算；GPT-4o API 费用（论文用，代码不用）。当前公开材料**无法给出可执行的最小预算**，因为代码缺失。 |
| **Q8** | **评测可行、复现不可行。** 5×A40 显存/算力足以跑 RLBench 推理与中小规模训练；但缺代码与权重，且 CoppeliaSim 4.1.0 + PyRep/RLBench 需要 Ubuntu 20.04 级环境（我们服务器是 CentOS 7，需容器化）。 |
| **Q9** | 移植到 RoboCombine 时，**忠实适配**只能是"VLM 输出技能序列 + 指令切换"；**已经改变算法**的部分是：用夹爪/接触判定代替 goal-pose 完成、用 home 复位或直接切换代替 chaining、用 Motus 的 chunk 动作代替 RVT/3DDA/ARP。 |
| **Q10** | **明确阻塞并转其他 baseline**：F1 = `BLOCKED_MISSING_CODE`。可向作者索取 chaining 实现与 DeCoBench 划分；不建议自行补写"看起来合理"的 DeCo。 |
