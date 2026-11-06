# 交接说明（给下一位执行 SkillHandoffBench 的 agent）

本文件包含：**服务器与环境事实**、**已验证的旧项目状态**、**硬约束**、**Phase 0C/1 的执行 Gate**、
**B0–B7 研究设计与指标**、**交付物与验收格式**。
所有路径与数字都来自 2026-11-06 的实际检查；未验证的项目已明确标注 `UNVERIFIED`。

---

## 0. 你的任务（一句话）

在 **不改动 Simulate、不训练 VLA** 的前提下，审计 RoboCombine 的可运行性，跑通**至少一个
checkpoint-backed 的官方 baseline rollout**（Motus + Oracle HSE），产出可审查的日志与统计，
并给出 `GO / PIVOT / BLOCKED` 决策。

---

## 1. 服务器访问（凭据不入库）

| 项 | 值 |
| --- | --- |
| 主机 | `222.29.51.96`，端口 `22` |
| 用户 | `lijh` |
| 密码 | **不写入仓库**；由用户单独提供，或本地 `configs/resources.local.env`（已被 `.gitignore` 排除） |
| 工作根 | `/scratch/lijh`（ext4，15T；**2026-11-06 清理旧 checkpoint 后可用 ≈232 GB**） |
| 系统 | CentOS 类，内核 4.x 代；`nvidia-smi` driver **550.120** |
| GPU | **5 × NVIDIA A40 46,068 MiB**（index 0–4），审计时全部空闲（≈1 MiB / 0% util） |
| 本地联机方式 | 旧项目自带 `D:\python\simulate\server\remote.py`（paramiko，`run/put/get`），可直接复用；密码经环境变量 `SIMULATE_SSH_PASSWORD` |

```powershell
# 复用旧项目的远程工具（只读使用，不改它）
cd D:\python\simulate
$env:SIMULATE_SSH_PASSWORD='<向用户索取>'
python server\remote.py run "date; df -h /scratch | tail -1; nvidia-smi --query-gpu=index,memory.used --format=csv,noheader"
```

**磁盘**：清理后 ≈232 GB 可用（曾只有 19 GB）。RoboCombine + RoboTwin + Motus 仍须先估体积，
**先做体积审计再下载**（见 §4.4）。禁止在服务器上 `pip install` 覆盖现有环境。

---

## 2. 现有环境（已验证）

| 用途 | 路径 | 版本 / 说明 |
| --- | --- | --- |
| PyBullet / CPU 仿真 | `/scratch/lijh/simulate_vla/venv/bin/python` | **Python 3.10.18** |
| JAX / OpenPI 推理训练 | `/scratch/lijh/exp40/openpi/.venv/bin/python` | **Python 3.11.16** |
| OpenPI 源码 | `/scratch/lijh/exp40/openpi` | commit `215abfb217dbac7d5f1273282331b9b1866c0479` |
| Simulate 代码镜像 | `/scratch/lijh/exp40/repo` | 非 git 仓库，由本地同步 |
| 旧模型资产 | `/scratch/lijh/.cache/openpi/openpi-assets/checkpoints/pi05_droid` | **只有 pi05_droid**，没有 aloha/pi05 base |
| 训练数据 | `/scratch/lijh/exp43/export_v3` | 311 train（A90 170 / B90 141） |
| 最好的 LoRA 权重（4.4 Group B / 12000） | `/scratch/lijh/exp44/B/ckpts/lora_step12000.npz` | 1.73 GB；需要服务时现合并 |

**注意**：官方 RoboCombine 的 Motus 与 pi05 adapter **使用不同的 Python 环境**。
不要把 Motus 装进现有 `openpi/.venv`，也不要覆盖 `simulate_vla/venv`。优先**新建独立 venv**
（但先确认磁盘够；否则用 `--system-site-packages` 或 miniforge 隔离）。

---

## 3. 旧项目 Simulate 的真实状态（只读，别改）

完整审计见 [`docs/00_simulate_4_7_audit.md`](00_simulate_4_7_audit.md)。要点：

| 层次 | 状态 | 数字 |
| --- | --- | --- |
| A 训练代码可运行 | ✅ | 4.4/4.5/4.6 三组训练完成 |
| B 专家动作可物理回放 | ✅ | 4/4（4.7）、8/8（4.2） |
| C 冻结 VLA 从独立初始状态自主成功 | ❌ | A90/B90 严格成功率 **0**；最好 1/20（4.2 B90 训练初态） |
| D 从前一技能终态继续 | ❌ **从未运行** | 无 A→B 组合 rollout |

4.7 契约验收结论（可直接引用）：训练/推理输入 **324/324 字段逐位一致**；Anchor-16 k0/k1–7 误差 **1e-16**；
专家回放 **4/4**、Oracle chunk **4/4**；控制器跟踪 0.012 rad；FK/EE 坐标系一致（0.0 m）；
离线 vs 在线 1.3–3.7e-3 rad。唯一 PARTIAL：图像是否比 state 晚一帧未逐帧验证。

旧项目最新提交：**`55fca58`**（`main`）。

---

## 4. Phase 0C：RoboCombine 可行性审计（先做，不跑 rollout）

### 4.1 获取代码并固定 commit

```bash
cd /scratch/lijh/SkillHandoffBench/third_party
git clone https://github.com/AutoLab-SAI-SJTU/RoboCombine.git
cd RoboCombine && git log -1 --format=%H   # 记录精确 commit 到 docs/01
```

**不要修改官方源码**。需要适配时写外部 wrapper 或最小可审计 patch，并在 `docs/01` 记录 diff。

### 4.2 必读文件

- `README.md`
- `docs/runtime_envs.md`
- `policy/Motus/README.md`
- `policy/pi05/README.md`
- `handoff_eval/specs/robocombine.json`
- `handoff_eval/runner/run_split.py`
- `tests/test_language_switch_runtime.py`

### 4.3 逐项确认（每项写 `AVAILABLE / MISSING / INCOMPATIBLE / UNVERIFIED`）

1. RoboTwin 仿真与任务资产是否存在、体积多少；
2. `Motus_robotwin2` checkpoint 是否可获取（体积、许可证）；
3. Motus 的 WAN 与 VLM 资源是否存在；
4. Python / CUDA / driver / 显存是否满足（driver 550.120，A40 48 GB，Python 3.10/3.11 已有）；
5. `pi05` adapter 的 embodiment / action space / 训练配置是否与**你手上的** checkpoint 兼容
   —— **`pi05_droid` 不能自动视为 `pi05_aloha_full_base`**（action dim、状态维、相机路数、机器人本体都可能不同）；
6. Oracle HSE 是否能在**没有 XVLA predictor** 时运行；
7. Ordered HSE 需要的 predictor bundle / X-VLA 是否具备；
8. benchmark 是否提供**原子阶段成功信息、切换事件、状态记录、物理成功标志**；
9. 能否在不改官方判据的前提下记录**交接前后状态**；
10. 外部资产许可证、访问权限、下载体积。

### 4.4 磁盘/体积预算（必须先做）

```bash
df -h /scratch
du -sh /scratch/lijh/* 2>/dev/null | sort -h | tail -20
```

当前 **≈19 GB 可用**。先估算 RoboTwin 资产 + Motus 权重 + venv 的总和；放不下就**不要下载**，
记录 `BLOCKED: disk` 并给出最小解决措施（向管理员扩容 / 清理已确认可再生成的旧合并参数，
**但不得删除 Simulate 的 checkpoint 与数据**）。

---

## 5. Phase 1：官方最小 baseline（Gate 1 → 2 → 3）

### Gate 1：CPU 与运行时检查（不算评测成功）

- 任务列表查询（官方 CLI，如 `--list-tasks`）；
- 官方轻量测试（如 `pytest tests/test_language_switch_runtime.py`）；
- 最小依赖 import；
- 路径与 checkpoint 完整性（sha256）；
- 记录运行参数与 GPU 可用性。

### Gate 2：1 任务 × 1 episode（Motus + oracle_hse）

选一个**两阶段、第一阶段有非零成功率、能观察到交接**的任务（依据官方 spec 与论文，不是"排名靠前"）。
完整保留官方最大步数与严格物理评价。记录：

- 任务 ID、**真实初始化 seed**（官方 runner 可能读 seed receipt，`--base-seed` 不保证生效）；
- checkpoint 路径 + 标识、两个 Git commit；
- 完整命令行、`--clear-cache` 取值、运行时长、GPU 使用；
- 原子阶段结果、是否发生切换、是否真正完成；
- 原始日志与统计文件路径。

### Gate 3：2 任务 × 5 episode（Oracle HSE）

固定 `--spec robocombine --track oracle_hse --policy Motus --episodes 5 --task-filter … --clear-cache false`。
只有 Ordered HSE 所需 predictor **已存在且无需新训练**时才尝试，否则记录阻断。

**硬约束**：单卡、不训练、不做 19 任务全量、单次 smoke **30 分钟 wall-clock 上限**（超时安全终止并留日志）、
不无人监管地跑长任务。

### 特别注意：`--clear-cache`

官方 runner 默认 `--clear-cache true`；论文里"保留当前 action chunk"的配置是 **`--clear-cache false`**。
复现时必须**显式固定**并写进 manifest，否则切换行为不可比。

---

## 6. 研究设计（Phase 1B，本轮只写方案不实现）

**研究问题**：在已知技能顺序、固定切换时机、冻结原子 VLA 的条件下，
**选择下游策略更容易执行的物理交接状态**，能否提升未知技能序列的组合成功率？

| 基线 | 内容 | 成本 |
| --- | --- | --- |
| B0 | 官方原子技能能力（单技能成功率） | 低 |
| B1 | 官方 Full Instruction | 低 |
| B2 | 官方 Ordered HSE | 中 |
| B3 | 官方 Oracle HSE（特权完成信号） | 中 |
| B4 | Oracle 切换时机下**直接交接**（无连接动作） | 中 |
| B5 | Oracle 切换时机下**随机合法位姿连接** | 中 |
| B6 | Oracle 切换时机下**规则/几何位姿连接** | 中 |
| B7 | Oracle 切换时机下 **Agent 选择交接状态**（下一阶段，本轮不做） | 高 |

B4–B7 必须共享：同一冻结底层策略、同一初始状态、同一切换时机、同一合法候选集合、同一规划工具权限。

**指标**（每项都要分子/分母）：

1. Ordered Success Rate
2. Stage-1 Success Rate
3. Transition Conversion（进入第二阶段的比例 / 成功切换数）
4. Handoff Physical Feasibility（规划可达、无碰撞、关节限位内）
5. Downstream Skill Success（交接后第二阶段成功率）
6. 交接额外步数 / 时间 / 碰撞次数

统计必须区分：**独立任务**、**独立初始状态**、**重复采样种子**；报告置信区间或 bootstrap。
任务选择在正式比较前固定，不允许为改善结果更换任务。

**概念边界（写进报告）**：
- Oracle HSE 是特权完成信号，**不等同于**视觉 Agent；
- Random 与 geometric handoff 必须允许**相同**的运动规划接口；
- 规划到"成功"不等于下游 VLA 成功；
- PRTI 改变训练分布，不能混入冻结策略的因果消融；
- 简化几何连接**不是** DeCo 复现，不可冒充 DeCo 成绩；
- 原子成功率过低时不要启动昂贵组合评测。

---

## 7. 本轮交付物

```
SkillHandoffBench/
├── README.md
├── prompt.md                      # 本文件
├── docs/
│   ├── 00_simulate_4_7_audit.md   # 已完成
│   ├── 01_benchmark_feasibility.md   # 待写：每项 AVAILABLE/MISSING/INCOMPATIBLE/UNVERIFIED + 命令证据
│   ├── 02_baseline_protocol.md       # 待写：B0–B7、任务选择、指标定义
│   ├── 03_execution_report.md        # 待写：真实执行记录（命令、seed、耗时、日志路径）
│   └── 04_go_no_go.md                # 待写：GO / PIVOT / BLOCKED + 证据
├── configs/resources.example.env  # 路径变量（无凭据）
├── scripts/preflight.sh           # 只读环境自检（已提供）
├── scripts/run_smoke.sh           # 待写：可复现的最小 benchmark 入口
└── results/<run_id>/              # run_manifest.json、summary.json、逐任务统计、完整日志
```

成功运行时保留 `run_manifest.json`、`summary.json`、逐任务 CSV 与完整日志；
平台阻断时也必须交付审计与可复用脚本，**不得伪造结果**。

---

## 8. 验收与决策格式

- **PASS**：4.7 进度清楚 + 新项目隔离 + 资源审计有证据 + 官方任务/依赖/指标核对 + **至少一个真实 checkpoint-backed rollout**；
- **PARTIAL**：审计与代码检查完成，但资源缺失无法跑真实模型（必须给出精确阻断 + 最小解决措施）；
- **FAIL**：假数据/测试桩冒充成绩、改判据、误用不兼容 checkpoint、覆盖旧实验、只写计划不检查。

最终必须回答：实际完成了什么；哪些失败或不可验证；是否建议暂停 Simulate 4.7；
是否建议 Motus + RoboCombine；是否值得进入 handoff-state selection；下一轮最小必要任务。
最后给出 **`GO / PIVOT / BLOCKED`**，每个判断附证据。

---

## 9. 红线（违反即 FAIL）

1. 不删除/覆盖 Simulate 的数据、日志、checkpoint、模型缓存；
2. 不对 Simulate 做破坏性 Git 操作（不 reset/clean/stash/force-push）；
3. 不修改 4.7 的训练/推理/评测代码，不改严格判据；
4. 不启动任何训练（LoRA / Action Expert / VLM 都不行）；
5. 不在共享服务器上 `pip install` 覆盖已有环境；
6. 不下载与现有资产重复的巨型 checkpoint；
7. 不用 `pi05_droid` 强行适配 RoboCombine 的 aloha action space 来"制造成功"；
8. 不用测试桩/假数据冒充真实模型 rollout；
9. 不在无人监管下跑长任务；不并行多卡；
10. 不提交服务器密码、密钥或大文件到 Git。
