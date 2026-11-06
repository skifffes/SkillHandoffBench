# SkillHandoffBench

零样本 VLA **原子技能组合（skill handoff）** 研究平台。目标 benchmark 是
[RoboCombine](https://github.com/AutoLab-SAI-SJTU/RoboCombine)（论文 https://arxiv.org/abs/2610.15425），
旧项目是 [Simulate](https://github.com/skifffes/Simulate)（已推进到实验 4.7）。

本仓库只做**组合/交接**层面的工作；原子技能训练与契约验证留在 Simulate，本仓库**只读引用**。

## 状态

| 阶段 | 状态 |
| --- | --- |
| Phase 0A：Simulate 4.7 审计 | **已完成**，见 `docs/00_simulate_4_7_audit.md` |
| Phase 0B：独立项目骨架 | **已完成**（本文件、`.gitignore`、目录结构） |
| Phase 0C：RoboCombine 可行性审计 | **未开始**（`third_party/RoboCombine` 尚未克隆） |
| Phase 1：官方 baseline smoke | **未开始**（依赖 0C 与 GPU/磁盘检查） |

下一轮执行者的完整交接说明在 **[`prompt.md`](prompt.md)**（服务器、路径、约束、Gate 与指标定义）。
服务器凭据**不入库**：放在本地 `configs/resources.local.env`（已被 `.gitignore` 排除）。

## 目录

```
SkillHandoffBench/
├── prompt.md                 # 交接说明：环境、约束、Gate、研究设计（给下一位 agent）
├── docs/
│   ├── 00_simulate_4_7_audit.md   # 旧项目真实进度（含证据路径与数字）
│   └── README.md                  # 待补：01_feasibility / 02_protocol / 03_execution / 04_go_no_go
├── configs/
│   └── resources.example.env      # 路径变量模板（无凭据）
├── scripts/
│   └── preflight.sh               # 只读环境自检（可重复运行）
├── third_party/                   # RoboCombine 将放在这里（不入库）
└── results/                       # 运行输出（不入库）
```

## 已验证可用的旧项目资产（只读）

- 服务器：`/scratch/lijh/exp40/repo`（Simulate 代码镜像，OpenPI commit `215abfb`）
- 数据：`/scratch/lijh/exp43/export_v3`（311 条训练集）
- checkpoint：`/scratch/lijh/exp4{4,5,6,7}/...`（LoRA / Action-Expert / 合并模型）
- 环境：`/scratch/lijh/simulate_vla/venv`（Python 3.10，PyBullet）、
  `/scratch/lijh/exp40/openpi/.venv`（Python 3.11，JAX/OpenPI）

**这些属于 Simulate，本仓库不修改、不删除、不重训。**
