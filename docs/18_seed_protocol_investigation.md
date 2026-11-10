# 18 · Seed 协议调查（Phase 4 第二阶段前置审计）

日期：2026-11-10。只读审计，未启动剩余 17 个任务，未改判据、未换 checkpoint。

标记：**VERIFIED**（有代码/原始数据直接支持）· **UNVERIFIED**（无法核实）· **MISMATCH**（已知不一致）。

---

## 1. 提交与数据核对

| 项 | 结论 |
| --- | --- |
| 本地 HEAD | `17ce88c`（Phase 4 Gate E 完成提交）**VERIFIED** |
| `docs/15` 的数字 | 与 `results/paper_table1/gateE_deep/**/evaluation_statistics.json` 逐条一致 **VERIFIED** |
| 四组 N=20 | oracle: living 7/20、office 9/20；full: living 2/20、office 0/20 ordered（2 次环境成功均乱序）**VERIFIED** |

---

## 2. 官方专家筛选逻辑（`script/eval_policy.py`）

| 行 | 行为 | 判定 |
| --- | --- | --- |
| 713 | `skip_successful=True`（默认） | **VERIFIED** |
| 717-719 | `priority_seeds_file` 存在时，先读成 `priority_seeds` | **VERIFIED** |
| 722-723 | 从 `*_successful_seeds.json` 载入 `successful_seeds` | **VERIFIED** |
| 724 | 从 `*_expert_demo_seeds.json` 载入已通过专家校验的 seed 集合 | **VERIFIED** |
| 731-732 | `task_env.suc = len(successful_seeds)`；`task_env.test_num = total_previously_tested` | **VERIFIED** |
| 761-762 | `all_seeds = priority_seeds(去重已成功) + range(st_seed, st_seed + test_num*20)` | **VERIFIED** |
| 775 | `skip_expert_demo = now_seed in expert_demo_seeds`（缓存命中则跳过专家） | **VERIFIED** |
| 777-790 | **未命中缓存时先跑专家 `play_once()`；若 `not (plan_success and check_success())` → `continue`** | **VERIFIED** |
| — | `continue` **不增加 `test_num`**，即被跳过的 seed **不进分母** | **VERIFIED** |

**结论 1：专家筛选在官方当前实现中默认启用**，且被跳过的 seed 完全不计入 episode 数。
也就是说"每任务 20 次"实际是"**20 个专家可行的初始状态**"。

**结论 2：`skip_successful=True` 使得"续跑同一个 save_dir"会排除已成功 seed 并补入新 seed**
→ 续跑会改变 episode 的 seed 组成。本轮四组深跑都是**单次跑完、未续跑**，所以不受影响（**VERIFIED**），
但下一轮若续跑必须显式说明。

**结论 3（关键）：能否证明论文也用这套筛选？`UNVERIFIED`。**
论文与仓库都没有发布 seed receipt / episode 级 seed 列表；`docs/13` 已记录论文未给 base seed 与筛选策略。

---

## 3. 实际使用的 seed（逐条）

### 3.1 深跑（N=20，base-seed 42 → st_seed 4300000）

| track | task | 实际 seed（20 个） | 候选区间 | 被跳过 |
| --- | --- | --- | --- | ---: |
| oracle_hse | living_room_tidy | `4300000-4300003, 4300005-4300011, 4300013-4300021` | 4300000–4300021（22 个） | **2**（4300004, 4300012） |
| oracle_hse | office_desk | `4300000-4300004, 4300006, 4300008, 4300010, 4300014, 4300015, 4300017, 4300018, 4300020, 4300023, 4300024, 4300026, 4300028, 4300029, 4300031, 4300034` | 4300000–4300034（35 个） | **15** |
| full_inst | living_room_tidy | `4300000-4300019`（连续 20 个） | 4300000–4300019（20 个） | **0** |
| full_inst | office_desk | `4300000-4300004, 4300006, 4300008, 4300010, 4300014, 4300015, 4300017, 4300018, 4300020, 4300021, 4300023, 4300024, 4300026, 4300028, 4300029, 4300031` | 4300000–4300031（32 个） | **12** |

### 3.2 **MISMATCH：两条轨道在 N=20 上不是配对设计**

| task | 交集 seed 数 | 只在 oracle | 只在 full |
| --- | ---: | --- | --- |
| living_room_tidy | 18 | 4300020, 4300021 | 4300004, 4300012 |
| office_desk | 17 | 4300034 | 4300021 |

→ `docs/15` §2 里 oracle 35% 与 full 10% 的对比，**不是同一批初始状态上的对比**，
差值里混入了"seed 不同"这个因素。**只有 Gate D 预检（3 seed）是真正配对的**（4300000–4300002 两轨道相同）。

### 3.3 观察到的事实：同一 seed 的专家校验结果会变

`4300004` 与 `4300012` 在 **oracle 轨道**专家失败被跳过，但在 **full_inst 轨道**通过并被评测。
两个轨道的 `setup_demo(seed)` 与专家 `play_once()` 代码路径相同 → **专家校验并非严格确定性**（**VERIFIED 观察**；
原因未定位，可能与 mplib/CuRobo 规划的随机性或超时有关，**UNVERIFIED**）。

这条很重要：它说明"配对"不能靠"同时启动两条轨道"来保证，只能靠**显式固定 seed 列表**——
而 `run_split.py` **不支持** `--priority_seeds_file`（只有 `eval_policy.py` 支持，见 §5）。

---

## 4. 关于 25.7% / 31.8% 的定性

上一轮口头给出的"不过滤估计"（office oracle 25.7% = 9/35、living oracle 31.8% = 7/22）是
**反事实估计**：把被跳过的 seed **假设为必然失败**后重算的分母。它们**不是实测**。

- 这些被跳过的 seed 上，**专家**都做不成（否则不会被跳过），策略几乎必然也失败——但**没有实测**。
- 因此这些数字只能用于"解释差距的量级"，**不能写进任何结果表当作复现成绩**。
- 若要做真·无筛选实测，必须绕过 `continue`（改代码或直接调 `eval_policy` 并伪造 `expert_demo_seeds`），
  这会**改变官方协议**，本轮**不做**。

---

## 5. `priority_seeds_file` 的真实可用性

| 入口 | 是否支持 | 证据 |
| --- | --- | --- |
| `run_split.py` | **否** | 其 argparse 无该参数；实测传 `--priority_seeds_file` → `exit=2` |
| `eval_policy.py` | **是** | 参数在 `overrides` 里读取（`usr_args.get("priority_seeds_file")`，行 698/718） |
| spec（`robocombine.json`） | 无 `seed_receipt` 字段 → run_split 不会传该参数 | **VERIFIED** |

→ 想固定 seed 只能**绕过 runner 直接调 `eval_policy.py`**（Phase 3 用过此法）。
本轮第二阶段改用 `--base-seed 45`（st_seed=4600000）以避开历史 seed，**但仍无法保证两轨道同 seed**。

---

## 6. 其余协议项复核

| 项 | 值 | 判定 |
| --- | --- | --- |
| Motus checkpoint | `Motus_robotwin2`，`mp_rank_00_model_states.pt` 16,046,580,367 B，sha256 `70bc1741…300eb65` | 文件 **VERIFIED**；与论文同一份 **UNVERIFIED** |
| checkpoint revision | 无 HF revision 记录 | **UNVERIFIED** |
| 仿真 | SAPIEN 3.0.0b1 + RoboTwin2.0 资产 | **VERIFIED**（本地）；与论文版本一致 **UNVERIFIED** |
| 最大步数 | 1500（spec 默认） | **VERIFIED**；论文是否 1500 **UNVERIFIED** |
| chunk 执行 | `--clear-cache false` → 缓存排空才切换（论文 Eq.4-5 chunk-preserving） | **VERIFIED** |
| episodes | 显式 `--episodes 20`（spec 默认 5） | **VERIFIED**；论文 20 **VERIFIED**（论文 §3.1 明写 380=19×20） |
| 官方 commit | `df237b22bd5c39d705b103daf2b9a8a168c9d453`（2026-10-15） | **VERIFIED** |
| 判据 | 未改；`sr_ordered` 用官方 `sequential` 语义（s1_step ≤ s2_step，且需两阶段都完成） | **VERIFIED** |

---

## 7. 审计结论

| 问题 | 结论 |
| --- | --- |
| 专家筛选是否默认启用？ | **是**（`eval_policy.py:777-790`，跳过不计数） |
| 现有证据能否证明论文用同一机制？ | **不能**（`UNVERIFIED`，无 seed receipt） |
| 两轨道是否配对？ | **N=20 时不配对（MISMATCH）**；只有 3-seed 预检配对 |
| 25.7%/31.8% 可用吗？ | **不可当结果**，只能当量级解释（反事实估计） |
| 能否固定 seed？ | run_split **不能**；只能直接调 `eval_policy.py --priority_seeds_file` |

**因此第二阶段（3 个新任务）必须**：用 `--base-seed 45` 的新 seed、逐条记录实际 seed、
并把"两轨道 seed 是否一致"作为验收项；不一致就报 `MISMATCH` 而不是硬凑配对。
