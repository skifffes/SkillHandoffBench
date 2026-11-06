# SkillHandoffBench

零样本 VLA **原子技能组合（skill handoff）** 研究平台。目标 benchmark 是
[RoboCombine](https://github.com/AutoLab-SAI-SJTU/RoboCombine)（论文 https://arxiv.org/abs/2610.15425），
旧项目是 [Simulate](https://github.com/skifffes/Simulate)（已推进到实验 4.7）。

本仓库只做**组合/交接**层面的工作；原子技能训练与契约验证留在 Simulate，本仓库**只读引用**。

## 状态（2026-11-07 01:30 CST 实测）

| 阶段 | 状态 | 证据 |
| --- | --- | --- |
| Phase 0A：Simulate 4.7 审计 | **已完成** | `docs/00_simulate_4_7_audit.md` |
| Phase 0B：独立项目骨架 | **已完成** | 本文件、`.gitignore`、目录结构 |
| Phase 0C：RoboCombine 可行性审计 | **已完成**（10 项逐条判定） | `docs/01_benchmark_feasibility.md` |
| Phase 1 Gate 1：CPU/运行时检查 | **PASS**（19 任务、38 pytest、渲染 OK、sha256） | `docs/03 §2` |
| Phase 1 Gate 2：Motus + oracle_hse 真实 rollout | **PASS（1/1 成功）** | `results/gate2_20261107_010606_*/` |
| Phase 1 Gate 3：2 任务 × 5 episodes | **PASS（9/10 成功；阶段1 10/10、切换 10/10）** | `results/gate3a_*`、`results/gate3b_*` |
| Phase 1B：B0–B7 研究设计 | **方案已固定**（未实现） | `docs/02_baseline_protocol.md` |
| 决策 | **GO（有条件）** | `docs/04_go_no_go.md` |

一句话结论：**官方 Motus checkpoint 在本机用官方判据完成了两阶段组合任务，oracle HSE 的交接事件
（cue step 51 → switch step 64，`cache_cleared=false`）被完整记录。**

## 目录

```
SkillHandoffBench/
├── prompt.md                       # 交接说明（给执行者）
├── docs/
│   ├── 00_simulate_4_7_audit.md    # 旧项目真实进度
│   ├── 01_benchmark_feasibility.md # RoboCombine 10 项可行性 + 12 项环境坑的根因
│   ├── 02_baseline_protocol.md     # B0–B7、任务选择、指标定义
│   ├── 03_execution_report.md      # 真实命令/seed/耗时/日志路径
│   ├── 04_go_no_go.md              # GO / PIVOT / BLOCKED + 触发条件
│   └── patches/                    # 对官方源码的最小可审计 patch（2 个）
├── configs/resources.example.env   # 路径变量模板（无凭据）
├── scripts/                        # 下载 / 建环境 / 构建 CuRobo / 跑 Gate / 整理结果
├── results/
│   └── gate2_20261107_010606_robocombine_oracle_hse_motus/
│       ├── run_manifest.json       # 运行元数据（commit/checkpoint/sha256/seed）
│       ├── summary.json            # 6 个指标（带分子/分母 + Wilson 95%）
│       ├── per_task.csv / episodes.csv
│       └── official/               # 官方原始产物（task.log、evaluation_statistics.json）
└── third_party/                    # 代码克隆（不入库）
```

## 复现（服务器）

```bash
cd /scratch/lijh/SkillHandoffBench
bash scripts/preflight.sh --server       # 只读自检
bash scripts/fetch_assets.sh assets      # RoboTwin2 资产 14.9 GB
python scripts/fetch_models.py --jobs 5  # Motus + Qwen3-VL
bash scripts/fetch_wan.sh                # Wan2.2 子集（T5+VAE）
bash scripts/setup_motus_env_v2.sh       # 独立 venv（不碰旧环境）
bash scripts/fix_env.sh                  # numpy/diffusers/omegaconf/opencv 收尾
bash scripts/setup_x11.sh                # X11 运行库（RPM 解包，无需 root）
bash scripts/setup_nvcc.sh               # micromamba + nvcc 12.1
bash scripts/build_curobo076.sh && bash scripts/build_curobo_retry.sh
bash scripts/run_smoke.sh gate1
bash scripts/run_smoke.sh gate2
EPISODES=5 bash scripts/run_smoke.sh gate3
```

**这些属于 Simulate 的资产，本仓库不修改、不删除、不重训**：
`/scratch/lijh/exp40/repo`、`/scratch/lijh/exp43/export_v3`、`/scratch/lijh/exp44/B/ckpts/lora_step12000.npz`、
`/scratch/lijh/simulate_vla/venv`、`/scratch/lijh/exp40/openpi/.venv`。

服务器凭据**不入库**：放在本地 `configs/resources.local.env`（已被 `.gitignore` 排除）。
