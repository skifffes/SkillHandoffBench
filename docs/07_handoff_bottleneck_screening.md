# 07 · 多任务交接瓶颈筛查（Gate C）

> 状态：**排队中**（Gate B 跑完后自动开始）。本文件先固定任务集、seed、统计口径；
> 数字在跑完后填入，未填一律 `pending`。

---

## 1. 任务集（**在执行前固定**，不按成功率挑选）

在 Phase 1 的两个任务之外，按"下游技能类型 / 接触需求"覆盖度选 5 个：

| # | 任务 | 第一阶段 | 第二阶段（下游技能） | 选择理由（技能类型） |
| --- | --- | --- | --- | --- |
| 1 | `arrange_sign_2tasks` | Sort objects | **Rotate QR code** | 旋转/对准类，对末端姿态敏感 |
| 2 | `breakfast_prep_2tasks` | Place cup on coaster | **Place bread in basket** | 放进容器（有包围/遮挡） |
| 3 | `desk_arrange_2tasks` | Move stapler to pad | **Place phone on stand** | 薄物体 + 立式支撑（放置约束更强） |
| 4 | `office_organize_2tasks` | Place mouse on pad | **Stamp seal** | 垂直按压动作（接触力方向不同） |
| 5 | `bakery_close_2tasks` | Place bread in basket | **Turn switch** | 小物件精细操作（夹爪精度要求高） |

**这 5 个不是按成功率挑的**；选择依据是任务书给定的"覆盖不同下游技能与接触需求"。
一旦 Gate C 开始，**不允许**因为结果不好而换任务。

---

## 2. 受控条件

| 项 | 取值 |
| --- | --- |
| checkpoint | `Motus_robotwin2`（sha256 `70bc1741…`） |
| track / policy | `oracle_hse` / `Motus` |
| 初始状态 | `--base-seed 42` → 每任务 seed `4300000, 4300001, 4300002`（执行前已写入 `results/phase2/seed_plan.json`） |
| 成功判据 | 官方 `check_success()`，未改 |
| 步数上限 | 1500（spec 默认） |
| clear-cache | `false` |
| 每任务 episode | 3 |
| 合计 rollout | **15** |

**不允许**：反复改 seed 去找期望的失败案例。若某 seed 的专家 demo 失败而被跳过，
必须记录实际使用的 seed（`episodes.csv` 里有）。

---

## 3. 指标定义（每个都要分子/分母）

| 指标 | 定义 |
| --- | --- |
| Stage 1 success | `s1_completed=True` 的 episode / 该任务的 episode 数 |
| Stage 2 success | `s2_completed=True` 的 episode / 该任务 episode 数 |
| Ordered success | `success=True` 的 episode / 该任务 episode 数 |
| **Transition conversion** | **Stage 2 success / Stage 1 success**（任务书定义） |
| 另一口径 | 已发生切换的 episode 中第二阶段成功的比例（`downstream_success_among_switched`） |
| 切换事件数 | 该任务所有 episode 的 `switch_events` 总数 |
| 首次失败位置 | `stage1` / `stage2` / `post_success_check` 计数 |
| 完成步数 | `total_steps` 的 mean/min/max；成功 episode 的 `s2_step` |

实现：`scripts/collect_phase2.py`（分子分母 + Wilson 区间，输出 `tasks.csv`/`episodes.csv`/`summary.json`）。

---

## 4. 判定规则（写死，避免事后解释）

| 观察 | 归因 |
| --- | --- |
| 第一阶段从未成功（`s1_completed` 全 False） | **原子能力瓶颈**，不能归因于交接 |
| 第一阶段成功、切换发生、第二阶段多次失败 | **潜在交接问题**（仍需 Gate D 的受控实验确认原因） |
| 第一阶段成功、但第二阶段从未被切换（无 switch event） | HSE/指令传递问题，不是交接状态问题 |

---

## 5. 结果（跑完后填）

### 5.1 逐任务

| Task | Stage 1 | Stage 2 | Ordered | Transition Conversion | Switch events | 首次失败位置 | 步数 mean/max | Candidate? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| arrange_sign_2tasks | pending | pending | pending | pending | pending | pending | pending | pending |
| breakfast_prep_2tasks | pending | pending | pending | pending | pending | pending | pending | pending |
| desk_arrange_2tasks | pending | pending | pending | pending | pending | pending | pending | pending |
| office_organize_2tasks | pending | pending | pending | pending | pending | pending | pending | pending |
| bakery_close_2tasks | pending | pending | pending | pending | pending | pending | pending | pending |

### 5.2 逐 episode

见 `results/phase2/gateC_screening/_summary/episodes.csv`。

---

## 6. 结论（跑完后填）
