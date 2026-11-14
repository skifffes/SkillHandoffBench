# 34 · DeCo 最小实验预注册

**状态：`NOT_READY`**

日期：2026-11-14。依据：`docs/32_deco_method_code_audit.md`（F1 = `BLOCKED_MISSING_CODE`）、
`docs/33_deco_resources_protocol_audit.md`。

> 本文件**不包含可执行参数**。F1 未通过（缺 chaining 实现、缺 DeCoBench 划分、缺示范数据、缺原子权重），
> 因此不写假设数值、不写 seed、不写样本量。**在状态改为 `READY` 之前，不得启动任何 DeCo 训练或 rollout。**

---

## 1. 未就绪的硬门槛

| # | 门槛 | 状态 | 说明 |
| --- | --- | --- | --- |
| 1 | 空间感知 chaining 实现（cost map + chaining poses） | ❌ 公开代码中不存在 | 全仓 0 命中；执行循环只剩 home 复位 |
| 2 | DeCoBench 12 任务划分与 variation | ❌ 未公开 | 只有 vendored RLBench `.ttm` 同名任务 |
| 3 | 4 源任务 × 50 示范 | ❌ 未公开 | 需按 `collect_dataset_train_*.sh` 自行采集（非 DeCoBench 划分） |
| 4 | RVT-2/3DDA/ARP 的 DeCoBench 权重 | ❌ 未定位 | 仓库 0 权重文件 |
| 5 | GPT-4o 或等价的"零样本 prompt" planning | ⚠️ 论文用 API；代码用微调 Qwen | 不等价 |
| 6 | CoppeliaSim 4.1.0 + PyRep/RLBench 运行时 | ⚠️ 需容器化（CentOS 7） | 未搭建 |

---

## 2. 若将来 READY，必须提前固定的内容（占位）

| 项 | 要求 |
| --- | --- |
| 实验假设 | 必须是论文 Table II 的可证伪对照（Base vs +DeCo），不得自创指标 |
| 实验组 | 至少 Base（原子策略）与 +DeCo；VLM 版与 rule 版必须分开标注 |
| 控制变量 | 低层模型、训练数据、评测 episode 数、seed、最大步数、观测配置 |
| seed | 必须记录 3 个 seed 具体控制什么（策略采样/初始位姿/材质），并与论文对齐 |
| 样本量 | 12 任务 × 20 demos × 3 seeds（论文）或明确说明偏离 |
| 成功判据 | 原版 `task.success()`；**不得**换成 RoboCombine 的 `sr_ordered` |
| 统计方法 | 原始计数 + Wilson 95% CI；原子 SR 与组合 SR 分表 |
| 停止条件 | chaining 失败/规划超时/episode 中断都计入并报告，不得静默续跑 |
| 泄漏声明 | 必须声明低层模型是否见过组合任务；用多级数据训练的模型单列 |

---

## 3. 状态变更条件

同时满足以下三条才可改为 `READY`：

1. 拿到 chaining 实现（或算法级描述 + 超参），并能在 DeCoBench 任务上跑通 **1 个 episode**；
2. 拿到 DeCoBench 划分 + 示范/权重，并在 `configs/deco_reproduction_audit.yaml` 中更新资源状态（附 sha256）；
3. 在 `docs/33` 增补一节记录版本与来源，并重新评估 F1（至少能到 `GO_MINIMAL`）。

---

## 4. 如果只能做"部分组件"

可做的部分（代码完整、可跑）：

- **VLM 下一子任务预测**（离线准确率，`src/high_level/eval.py`）；
- **`half` 模式**下的指令切换执行（`--eval_mode half`）。

但两者都**不是 DeCo**：
前者没有机器人执行，后者用的是**夹爪变化 + home 复位**而不是 goal-pose + chaining。
若做，只能命名为 **"RoboHiMan 分层评测复现"**，并注明与 DeCo 的差异（`docs/32 §4`）。

---

## 5. 当前建议

**阻塞 DeCo，等待作者资源；不自行补写 chaining。**
若需要继续推进主线 baseline，应先做 B3/B4 的可行性审计，而不是在这里等待。
