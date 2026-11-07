# 09 · 下游原子技能 B 的独立能力（Gate A 完整性审计 + Gate C B0 基线）

> 状态：Gate A 已完成；Gate C 的 B0 **入口审计已完成**（可行），rollout 结果在 §4 追加。

---

## 1. Gate A：评测结果完整性审计

### 1.1 方法

`scripts/check_phase2_integrity.py`（只读）对每个 `tasks/<task>/` 目录独立判定 5 个字段：

| 字段 | 含义 |
| --- | --- |
| `process_exit_code` | 子进程退出码（从 runner 日志 `END task=... code=N` 解析） |
| `evaluation_complete` | stats 可解析 + 字段齐全 + episode 数 = seed 数 + 无重复 seed + `task.log` 步数不越界 + `_result.txt` 存在 + `command.sh` 的 checkpoint/task 匹配 |
| `environment_success` | 官方环境判据（所有子任务完成 + 夹爪张开）通过的比例 |
| `ordered_success` | 官方 `sr_ordered` 语义：子任务**按顺序**完成（`s1_step <= s2_step`），**不要求**终局夹爪条件 |
| `post_eval_crash_suspected` | 退出码为负（信号）**且** `_result.txt` 已写出 → 疑似"评测后崩溃" |

### 1.2 结果（14 个 task 目录，覆盖 Phase 1 + Phase 2 全部运行）

```
task                              exit complete env_succ  ordered crash?  problems
living_room_tidy_2tasks            -11     True      1/1      1/1   True  -
living_room_tidy_2tasks            -11     True      1/1      1/1   True  -
living_room_tidy_2tasks            -11     True      5/5      5/5   True  -
office_desk_2tasks                 -11     True      4/5      4/5   True  -
living_room_tidy_2tasks            -11     True      1/5      1/5   True  -     <- Phase2 full_inst
office_desk_2tasks                 -11     True      1/5      0/5   True  -     <- Phase2 full_inst
arrange_sign_2tasks                -11     True      0/3      1/3   True  -
bakery_close_2tasks                -11     True      2/3      3/3   True  -
breakfast_prep_2tasks              -11     True      3/3      3/3   True  -
desk_arrange_2tasks                -11     True      2/3      2/3   True  -
office_organize_2tasks             -11     True      2/3      2/3   True  -
（A/B 三次 living_room 各 1/1、1/1）
14 task dirs, 0 with problems
```

**结论**：
1. **完整性检查 14/14 通过，0 problems** —— episode 数=seed 数、终局事件存在、JSON 可解析、`_result.txt` 与 `task.log` 一致、命令归属（checkpoint/task/track）匹配。
2. `process_exit_code = -11` 出现在**全部** 14 个目录，且 `_result.txt` 全部存在、stats 全部完整 →
   `post_eval_crash_suspected = True`：**评测后**的解释器析构段错误，**不是**评测失败。
   按任务书要求，**没有**把它改写成 0，也没有隐藏。

### 1.3 关键修正：`sr_ordered ≠ episode success`（用户要求审计的案例）

官方定义（`handoff_eval/summary/summarize_split.py:38-55`）：
`sr_ordered = subtask_completion.sequential[f"subtask_1_to_{N}"].rate`，
而 `sequential` 由 `eval_policy.py:576-593` 判定：`s1_step <= s2_step` 才算按序完成。
**它不包含"夹爪张开"这个终局条件**，episode success 才包含。

因此：

| 案例 | 环境 success | `sr_ordered` | 判定 |
| --- | --- | --- | --- |
| Phase 2 full_inst `office_desk` seed 4300001（`s2@359 < s1@655`） | ✅ | ❌ | **不是 ordered success** —— 用户指出的这个案例确认**不能算作有序成功** |
| Phase 2 full_inst `office_desk` 该 run 合计 | 1/5 | **0/5** | 上一轮报告写的 "1/5" 是**环境成功率**，不是 `sr_ordered` |
| Phase 2 Gate C `arrange_sign` | 0/3 | **1/3** | 反向背离：有 1 个 episode 双阶段**按序完成**，但终局夹爪没达标 |
| Phase 2 Gate C `bakery_close` | 2/3 | **3/3** | 同上 |

→ **上一轮 `docs/06`/`docs/07` 表格里的 "Ordered Success" 列实际是 `episode_success_rate`**。
本轮起，凡是"ordered success"一律指官方 `sr_ordered`，并**同时报告** environment success，
两个数分开写（见 §4 与 `docs/10`）。这是 Gate A 最重要的产出之一。

---

## 2. Gate C 前置审计：能否构造**合法**的 B0？

### 2.1 资源审计

| 项 | 结果 |
| --- | --- |
| RoboCombine 公开仓库是否含原子任务 env | ❌ 不含（只有 19 个 `*_2tasks` 组合任务，`envs/` 里没有 `place_phone_stand.py` / `stamp_seal.py`） |
| 服务器上是否已有 RoboTwin 安装 | ❌ 没有 |
| 上游 RoboTwin 是否可取 | ✅ `github.com/RoboTwin-Platform/RoboTwin`（depth 1 克隆，`envs/` 共 54 个原子任务，含 `place_phone_stand.py`、`stamp_seal.py`） |
| 上游原子 env 的 import 是否与 RoboCombine 兼容 | ✅ 同样 `from ._base_task import Base_Task` / `from .utils import *`；把两个原子 env 文件放进 `envs/` 即可被 `class_decorator` 加载（**只新增文件，不改任何官方文件**） |
| 资产 | ✅ 复用已有 RoboTwin2.0 assets（同一套 `objects/embodiments`） |

### 2.2 合法性论证（为什么这算"官方原子起点"，不是硬重置）

- 使用的是 **RoboTwin 官方原子任务 env 的 `load_actors()`**：物体位置/姿态由该原子任务自己的
  `rand_pose(xlim, ylim, qpos)` 采样，**不是**我们手工摆放，也不是把组合任务的物体位置搬过来；
- 初始状态由 `setup_demo(seed=...)` → `_init_task_env_` 生成，与官方评测流程一致；
- 成功判据是该原子任务自己的 `check_success()`（未经修改）；
- 指令使用官方阶段指令文本（`place_phone_stand` → "Place phone on stand"，
  `stamp_seal` → "Stamp seal"），与组合任务第二阶段完全一致；
- **没有** reset 物体、没有改 success 判据、没有改机器人初始位姿。

### 2.3 依赖与风险（已实测）

| 风险 | 实测结果 |
| --- | --- |
| 上游原子 env 调用 RoboCombine 裁剪版 `_base_task` 里不存在的方法 | ✅ `place_phone_stand` 与 `stamp_seal` 的 `setup_demo`/`play_once`/`check_success` 都跑通 |
| 原子 env 没有 `subtask_completed` 属性 | ✅ 无影响：`eval_policy` 会退化为 `num_subtasks=1`，`full_inst` 不需要切换 |
| 专家 demo 是否可解 | ✅ 两个任务各 1 个 seed 冒烟：`plan_success=True, strict_check_success=True` |

**冒烟证据**（`logs/` 与命令见 §5）：
```
[sim_smoke] task=place_phone_stand seed=100042
[sim_smoke] setup_demo OK in 33.9s; subtasks=0
[sim_smoke] play_once OK in 2.1s
[sim_smoke] plan_success=True strict_check_success=True
[sim_smoke] task=stamp_seal seed=100042
[sim_smoke] setup_demo OK in 30.7s; subtasks=0
[sim_smoke] play_once OK in 3.2s
[sim_smoke] plan_success=True strict_check_success=True
```

**判定：B0 入口 = 合法且可执行** → 允许进入 §4 的 10 次 rollout。

### 2.4 B0 与 A→B 交接场景的**已知差异**（必须写进结论）

| 维度 | B0（原子） | A→B（组合第二阶段） |
| --- | --- | --- |
| 物体初始位置 | 由原子任务自己的 `xlim/ylim` 采样 | 由**组合任务**的 `load_actors` 采样 |
| 第一阶段物体 | 不存在 | 存在（已被移动过，可能挡路/改变场景） |
| 机器人初始位姿 | 原子任务 homestate | **第一阶段结束时的位姿**（这就是"交接状态"） |
| 夹爪状态 | 张开 | 可能是刚放下的状态 |
| 指令 | 单条原子指令 | 同一条原子指令（oracle 切换后） |

→ **B0 高 ≠ 交接一定没问题；B0 低也不能全归因于机器人位姿**，因为物体分布本身不同
（物体几何/位置差异同样是混杂因素）。这一点在 `docs/11` 里会作为"不能过度归因"的依据。

---

## 3. Gate A 对上一轮报告的两处更正（记录在案）

| # | 上一轮写法 | 更正 |
| --- | --- | --- |
| 1 | `docs/06` 表 "Full Inst ordered success = 2/10" | 其中 1 个 episode 是**乱序**完成（office 4300001），
按官方 `sr_ordered` 应为 **1/10**；`episode_success=2/10` 仍然成立（两个数含义不同） |
| 2 | `docs/07` 表 "Ordered Success" 列 | 实为 `episode_success_rate`；官方 `sr_ordered` 分别是
arrange_sign **1/3**、bakery **3/3**、breakfast **3/3**、desk **2/3**、office_organize **2/3** |

---

## 4. Gate C：B0 rollout 结果（10 次，`full_inst` 单条原子指令）

运行：2026-11-07 18:19–19:03。命令 `bash scripts/run_phase3.sh c`；产物 `results/phase3/gateC/`。

| Task（原子） | 指令 | B0 环境 success | 步数 mean/min/max | 实际 seeds |
| --- | --- | --- | --- | --- |
| `place_phone_stand` | Place phone on stand | **4/5** | 337 / 45 / 1500 | `5300000, 5300001, 5300002, 5300004, 4300000` |
| `stamp_seal` | Stamp seal | **5/5** | 129 / 45 / 336 | `5300003, 5300004, 4300001, 4300002, 4300003` |

**seed 说明（重要）**：`5300000–5300002` 在 `stamp_seal` 上**专家 demo 校验没过**，
`5300003` 在 `place_phone_stand` 上没过，于是官方循环按 `priority_seeds → range(4300000…)` 顺延补位。
所以两个任务**不是同一批初始状态**，任务间不能按 seed 配对比较。
（顺序为依据"优先列表 + 专家通过集合"的**重建**；官方 `evaluation_statistics.json` 对原子任务
**不写 `episode_details`**，见 §4.1 的已知缺口。）

`sr_ordered` 对原子任务没有意义（`num_subtasks=1` 且没有 `subtask_completed` 属性），
本表只用 `metadata.total_successes / total_episodes`。

### 4.1 已知记录缺口（诚实标注）

原子任务 env 没有 `subtask_completed`，`eval_policy.py:929` 的 `if hasattr(...)` 分支不成立，
因此 **`episode_details` 为空**：没有逐 episode 的 seed / s1_step / 成功标记。
本轮能给出的只有 `metadata`（episode 数、成功数）与 `episode_steps`（均值/最值），
以及 `*_expert_demo_seeds.json`、`*_successful_seeds.json`。**逐 episode 与 seed 的一一对应是重建的**，
不是日志直接给出的。下一轮若要严格配对，应在 B0 也开 `SHB_TRACE_JSONL`（`episode_start` 会带 seed）。

### 4.2 B0 的意义与**不能**推出的结论

- 能推出：**冻结 Motus 在合法原子起点上确实会做这两个下游技能**（4/5、5/5），
  所以 A→B 里同一技能失败，**不能**简单归因于"策略根本不会"。
- **不能**推出：A→B 失败 = 机器人位姿问题。B0 与 A→B 的**物体分布不同**（§2.4），
  这是与"机器人交接位姿"并列的混杂因素，必须分开才能谈因果。

---

## 5. 复现命令

```bash
cd /scratch/lijh/SkillHandoffBench
# 1) 原子 env 冒烟（不算评测成绩）
export ROBOCOMBINE_ASSETS_DIR=$PWD/third_party/RoboCombine/assets
export PYTHONPATH="$PWD/third_party/RoboCombine:$PWD/third_party/curobo076/src"
cd third_party/RoboCombine && python ../../../scripts/test_task_env.py place_phone_stand 100042
# 2) B0 评测（10 rollouts）
cd /scratch/lijh/SkillHandoffBench && bash scripts/run_phase3.sh c
# 3) 完整性检查（可随时重跑）
python scripts/check_phase2_integrity.py --run-root results/gate3a_* --run-root results/phase2 ...
```
