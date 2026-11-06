# Simulate 实验 4.7 进度审计（供 SkillHandoffBench 复用）

审计时间：2026-11-06 22:35 CST。审计方式：只读查看本地仓库、服务器文件与运行日志。
**本文件中的每个数字都能在标注的路径找到原始证据；没有基于 README 的 PASS 标签下结论。**

## 1. 仓库与工作区

| 项 | 值 |
| --- | --- |
| 本地仓库 | `D:\python\simulate` |
| 远端 | `https://github.com/skifffes/Simulate`，`main` |
| 最新提交 | **`55fca58`**（实验 4.7 Gate5 补第二个 checkpoint） |
| 工作区 | 有约 30 个未跟踪文件（历史 mp4/csv/trace 与 `_tmp/`），**未提交、未 stash、未清理** |
| 服务器代码镜像 | `/scratch/lijh/exp40/repo`（非 git 仓库，由本地 rsync/put 同步） |
| OpenPI | `/scratch/lijh/exp40/openpi`，commit `215abfb217dbac7d5f1273282331b9b1866c0479` |

## 2. 实验 4.2–4.7 的真实状态

### 4.2 动作契约与学习曲线
- 修复：Action Adapter、夹爪单位、fixed anchor、动作裁剪、权重导出。
- 证据：`results/experiment_4_2/contract_replay_p0c/final_report.md`。
- 关键数字：专家经 Adapter 回放 8/8 严格成功、目标误差 1e-17；
  旧数据 1800-step LoRA 在 B90 训练初态 **1/20** 严格成功，A90 **0/5**。

### 4.3 数据扩充
- A90 新增 **140**、B90 **113** 条严格成功示范（去重后），train 合计 **311**；
- 去重清单与逐文件 SHA256：`results/experiment_4_3/data_expansion/train_manifest_v2.json`、
  `selected_artifacts_sha256.json`；
- 导出数据：`/scratch/lijh/exp43/export_v3`（311 train / 16 val / 13 test，meta.jsonl）。

### 4.4 扩数据 + 12,000 updates（LoRA）
- 两组各 **12,000** updates：Group A（58 条）Group B（311 条），均从原始 `pi05_droid` 初始化；
- 离线（val 30 状态 × 4 seeds）：MAE 0.033（1200 步）→ **0.0071**（12000 步，Group B）；
- **物理闭环：0/8**；训练初态 B90 最好推进 0.153 m（4.2 的 1800-step 模型）与 0.170 m（4.4 B/12000）；
- 证据：`results/experiment_4_4/final_report.md`、`rollout_results.csv`。

### 4.5 Action Expert-only 全参数微调
- 冻结 VLM（32 张量 / 2923.3M），训练专家+投影 **430.1M（12.83%）**；
- 12,000 updates、3.70 epoch、峰值显存 34.4 GB、1.05 step/s；
- 离线与 LoRA 持平（MAE 0.0070 vs 0.0071），**闭环不优于 LoRA**：
  val 0/48 vs 0/48；训练初态 0/18 vs **1/18**（B90 推进中位 0.014 m vs 0.170 m）；
- 0.3×LR 救援实验：消除退化 checkpoint，但闭环更差（中位推进 0.000 m）；
- 证据：`results/experiment_4_5/final_report.md`、`paired_rollout_results.csv`、
  `paired_traininit_results.csv`。

### 4.6 少数完整 episode 的闭环过拟合
- 4 条严格成功 episode（A90 ep0/ep5、B90 ep0/ep2），164 窗口；
- 1,500 / 3,000 / 4,000 updates（36.6 / 77 / 97.6 epoch）：
  - 离线 MAE 0.024 → **0.0188**（仍不及 311 条模型的 0.007）；
  - **闭环 0/12、0/12、0/12**；
  - 3,000 步是峰值：B90 **6/6 都推动**（最远 0.175 m、**离墙 9.7 mm**）；
    A90 **2/6** 完成抓取+搬运+放置（两指重叠 826–1003 步），放置误差 **2.67/3.67 cm**；
  - 4,000 步退化（B90 推进回落到 0.001–0.083 m）。
- 证据：`results/experiment_4_6/overfit_report.md`、`rollout_results.csv`。

### 4.7 训练—推理—执行契约验收（本轮最新工作）
**结论：契约通过，唯一 PARTIAL 是"图像是否比 state 晚一帧"未逐帧验证。**

| 契约层 | 判定 | 关键数值 | 证据 |
| --- | --- | --- | --- |
| 训练 vs 在线输入（图像/state/prompt/token/mask） | PASS | **324/324 字段逐位一致，max abs = 0.0** | `results/experiment_4_7/observation_contract.csv` |
| Anchor-16 k0 / k1–7 | PASS | 1.1e-16 rad | `action_roundtrip.csv` |
| Anchor-16 k8–15 | PASS（含 0.35% 裁剪） | max 0.013 rad | `adapter_clipping_audit.json` |
| Adapter 改动专家动作 | PASS | 0/707 次限速；目标误差 0.0 | `expert_execution_trace.csv` |
| 专家逐周期物理回放 | PASS | **4/4 严格成功** | `oracle_chunk_results.csv` |
| Oracle 绝对目标 chunk（8 步） | PASS | **4/4 严格成功** | 同上 |
| 原始标签重锚定（B2） | 记录 3/4 | B90 ep2 因状态漂移失败 | 同上 |
| 控制器跟踪 / 夹爪 | PASS | 0.0121 rad / 0.0065 | `control_tracking_audit.md` |
| FK/EE 坐标系 | PASS | `pose()`=link11=FK，20 构型差 **0.0 m** | `fk_frame_audit.md`、`fk_consistency.csv` |
| 离线 vs 在线 Policy | PASS | 1.3–3.7e-3 rad（step3000）、1.3–2.2e-3 rad（B/12000） | `policy_inference_parity*.csv` |

**4.6 的 0.33 m FK 偏差已定性**：不是坐标系问题，是 4.6 诊断脚本自建场景与运行时场景不一致；
用运行时 EE 重算后 **tick0 偏差 0.0 m**，首次 >3 cm 出现在**第 1–2 个控制周期**
（`first_deviation_v2.csv`；注意这**不是**"不可恢复点"）。

## 3. 四个层次必须分开

| 层次 | 是否达成 | 证据 |
| --- | --- | --- |
| **A. 训练代码可运行** | ✅ | 4.4/4.5/4.6 共 3 组 12k/1.5k-4k 训练均完成，loss 有限、有 checkpoint |
| **B. 专家动作可物理回放成功** | ✅ | 4.7 模式 A **4/4**；4.2 8/8 |
| **C. 冻结 VLA 从**独立原子初始状态**自主成功 | ❌ | A90/B90 所有 checkpoint 严格成功率 **0**（最好 1/20 在 4.2 的 B90 训练初态） |
| **D. 冻结 VLA 从**前一技能真实终态**继续成功 | ❌ **从未运行** | 无 A→B 组合 rollout；4.2 起即被设计阻断 |

→ 这正是 SkillHandoffBench 要研究的问题（C→D 之间的交接）。**旧项目没有跑过 D 层**。

## 4. 仍然存在的失败与未解问题

1. **B90 终态精度**：最好离墙 9.7 mm、无墙接触；严格判据要求真实接触；
2. **A90 终态精度**：最好放置误差 2.67 cm；
3. **A90 抓取不稳定**：4.6 中 2/6 成功抓取；
4. **留出条件完全失败**：val（A90 y=0.21、B90 物体 y=0.27）两个模型 48/48 无接触；
5. **图像-状态时序未逐帧验证**（4.7 唯一 PARTIAL）；
6. **训练不稳定**：4.5 AE 在 6000/8000 步退化；4.6 在 4000 步退化（"甜点"现象）。

## 5. 可复用资产（只读）

> **2026-11-06 22:45 更新：用户授权清理已失效 checkpoint**（理由：Action Expert-only 无意义，必须 LoRA VLM）。
> 现只剩下表这些；`exp42` 旧训练 run、`exp45` 全部、`exp46/run`、`exp47/merged`、`exp44/A` 已删除，
> `/scratch` 可用空间从 **19 GB → 232 GB**。

| 资产 | 路径 | 说明 |
| --- | --- | --- |
| 训练数据 | `/scratch/lijh/exp43/export_v3` | 311 train（A90 170 / B90 141），256² 两路 v3 相机 |
| **最好的 LoRA 权重（4.4 Group B step12000）** | `/scratch/lijh/exp44/B/ckpts/lora_step12000.npz` | 1.73 GB；需要服务时用 `scripts/exp42/export_params_from_lora.py` 现合并 |
| 旧 LoRA（4.4 B step10000） | `/scratch/lijh/exp44/B/ckpts/lora_step10000.npz` | 1.73 GB，对照用 |
| 旧 90 条导出数据 | `/scratch/lijh/exp42/data` | 5.9 GB（4.2 用） |
| PyBullet 环境 | `/scratch/lijh/simulate_vla/venv` | Python 3.10.18，pybullet |
| OpenPI 环境 | `/scratch/lijh/exp40/openpi/.venv` | Python 3.11.16，JAX |
| 严格评价器 | `src/exp41/strict_eval.py` | `exp4.1-strict-v1.2`，阈值不可改 |

**已删除（记录在案，可重生成）**：`exp42/{run,run2,ab,ab_repr,curve600,curve1200,curve1800,curve2400,overfit}`
（约 153 GB 旧 LoRA 训练产物）、`exp45/*`（30 GB，Action Expert-only）、`exp46/run`（17 GB，4 条 episode 过拟合玩具）、
`exp47/merged`（25 GB，合并模型）、`exp44/A` 与 opt state。所有对应**结果 JSON/日志/manifest 仍在
`D:\python\simulate\results/` 与服务器 `exp4x/*.log`、`exp42/archive_meta/`** 中，指标不受影响。

## 6. 暂停 4.7 的代价

- 4.7 的契约验收**已完成并提交**（`55fca58`），暂停不会丢失任何未记录信息；
- 唯一未完成项（图像-状态时序逐帧验证）是**低优先级**：不影响"契约通过"的结论方向；
- 若后续回到 Simulate，建议只做两件小事：
  (a) 图像-状态时序的逐帧验证（渲染重放或互相关）；
  (b) 终态精度专项（墙前 5 cm、放置 2 cm 内）——这两件都与交接研究**互补**，不冲突。

## 7. 给 SkillHandoffBench 的直接结论

1. **不要在 Simulate 上继续做原子技能**：C 层已证明数据量/参数范围/步数都不是主因；
2. **不要假设 4.7 已验证组合能力**：D 层从未运行；
3. 交接研究可以直接建立在 RoboCombine 上，**不需要**把 Simulate 的 `pi05_droid` 迁过去
   （embodiment/action space 不同，见 `prompt.md` 的警告）。
