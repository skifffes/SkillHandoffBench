# 31 · PRTI 最小实验预注册

**状态：`NOT_READY`**

日期：2026-11-14。依据：`docs/30_prti_reproduction_audit.md`（判定 `BLOCKED`）。

> 本文件**不包含任何可执行的实验参数**，因为前置条件未满足。
> 下面只登记"如果资源到位，届时必须提前固定的变量"，以及"当前缺什么"。
> **在状态改为 `READY` 之前，不得启动任何 PRTI 训练或 rollout。**

---

## 1. 为什么是 NOT_READY

| 前置条件 | 状态 | 阻断来源 |
| --- | --- | --- |
| 官方 PRTI 实现（数据引擎 + 训练） | ❌ 不存在（仓库 0 命中） | `docs/30 §3` |
| π0.5 RoboTwin atomic checkpoint | ❌ 未公开 | `docs/30 §5` |
| PRTI 后训练权重 | ❌ 未公开 | `docs/30 §5` |
| ~10K 单技能训练数据 | ❌ 未公开 | `docs/30 §6` |
| data engine 算法描述 | ❌ 论文未给 | `docs/30 §2.6` |
| pi05 运行时 + openpi 训练栈 | ❌ 服务器上没有 | `docs/30 §4` |

**这六项任意一项缺失，"PRTI 原方法复现"就不成立。** 因此不写假设、不写样本量、不写 seed。

---

## 2. 一旦 READY，必须在此之前固定的内容（占位，不填数值）

| 项 | 要求 | 当前 |
| --- | --- | --- |
| 实验假设 | 必须引用论文 Table 2 的具体对照（Base / Random / Reset / PRTI） | 待定 |
| 实验组 | B0（无干预）、B1（官方 PRTI）、B2（官方 Oracle HSE）；可选 Random / Reset | 待定 |
| 控制变量 | checkpoint、task config、episodes、max steps、seed、切换协议 | 待定 |
| seed | 必须与 B0 冻结口径一致（base-seed 42 → 4300000 起），并记录 accepted seeds | 待定 |
| 样本量 | 与论文一致：20 episodes / 任务；任务数按资源决定（≥2） | 待定 |
| 成功判据 | 官方 `sr_ordered`（`subtask_completion.sequential`），env success 单独报 | 已冻结（B0） |
| 统计方法 | 原始计数 + Wilson 95% CI；不做跨基座的显著性合并 | 已冻结（B0） |
| 停止条件 | 任一任务出现 `PLANNER_HANG` 或超预算即停止并记录，不得静默续跑 | 已冻结（B0） |

---

## 3. 状态变更条件

只有同时满足以下三条，才可把本文件改为 `READY` 并填写数值：

1. 拿到**官方 PRTI 权重**或**官方训练代码 + π0.5 RobotWin atomic ckpt + 训练数据**；
2. 在 `configs/prti_reproduction_audit.yaml` 中把对应资源状态改为 `PUBLIC_AND_AVAILABLE`（附 sha256）；
3. 在 `docs/30` 增补一节记录资源来源与版本，并重新评估 Level（至少 Level 2）。

---

## 4. 当前建议

**不要为 PRTI 等待或自建近似实现。** 按 `docs/30 §13`，下一步转入 **DeCo（B2）**；
PRTI 保留为 `BLOCKED_EXTERNAL_RESOURCE`，等作者资源公开后再回到本文件。
