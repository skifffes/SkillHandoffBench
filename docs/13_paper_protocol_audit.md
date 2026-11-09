# 13 · 论文评测协议审计（Gate A）

论文：*Exploring the Limits of Combinatorial Generalization in Embodied Manipulation*
（arXiv:2610.15425v1，2026-10-11）。官方仓库 `AutoLab-SAI-SJTU/RoboCombine`，本地 commit
`df237b22bd5c39d705b103daf2b9a8a168c9d453`（2026-10-15）。

标注约定：`PAPER_SPECIFIED`（论文正文明确）/ `OFFICIAL_CODE_DEFAULT`（公开代码默认）/ 
`UPSTREAM_MODEL_SPECIFIED`（上游模型仓库规定）/ `INFERRED`（由两者共同推出）/ `UNKNOWN`（未公开）。

---

## 1. 逐项审计表

| # | 条件 | 取值 | 来源 | 与官方公开代码是否一致 |
| --- | --- | --- | --- | --- |
| 1 | Motus checkpoint | HF `motus-robotics/Motus_robotwin2`，`mp_rank_00_model_states.pt` = 16,046,580,367 B，sha256 `70bc1741…300eb65` | `UPSTREAM_MODEL_SPECIFIED` | 代码只接受路径，**论文未点名仓库** → `CHECKPOINT_PARITY_UNVERIFIED` |
| 2 | 仿真版本 | SAPIEN 3.0.0b1 + RoboTwin 2.0 资产（objects / embodiments / background_texture） | `UNKNOWN`（论文只说 "built on RoboTwin [5]"） | 我们用 RoboTwin2.0 公开资产，**论文所用版本未公开** |
| 3 | 19 个组合任务 | `handoff_eval/specs/robocombine.json` 的 `tasks`（19 项，`stage_count=2`） | `PAPER_SPECIFIED`（"19 novel multi-stage compositions"）+ `OFFICIAL_CODE_DEFAULT`（名单） | ✅ 名单完全来自官方 spec |
| 4 | 场景与随机化 | `task_config/robocombine_eval.yml`：`random_background: false`、`cluttered_table: false`、`clean_background_rate: 1`、`random_light: false`、`random_head_camera_dis: 0`、`random_table_height: 0` → **clean 场景** | `OFFICIAL_CODE_DEFAULT` | 论文只说 "20 rollouts per composition"，未给随机化细节 → 采用官方 eval config |
| 5 | 每任务 episode 数 | **20**（论文 380/19=20） | `PAPER_SPECIFIED` | ⚠️ **spec 默认是 5**（`default_episodes: 5`，README 也写默认 5）→ **必须显式 `--episodes 20`** |
| 6 | 每 episode 最大步数 | **1500** | `OFFICIAL_CODE_DEFAULT`（spec `default_max_steps_per_episode: 1500`） | 论文未写步数 → 只能沿用官方默认；属 `UNKNOWN` 风险项 |
| 7 | 初始 seed | `--base-seed 42` → `st_seed = 100000*(1+42) = 4300000`；spec 中**没有 `seed_receipt`** 字段 | `OFFICIAL_CODE_DEFAULT` | 论文**未给 base seed** → `SEED_PROTOCOL_PARITY_UNVERIFIED` |
| 8 | 专家成功筛选 | `script/eval_policy.py` 在每个 seed 上先 `setup_demo` + `play_once()`（专家），
`plan_success` 且 `check_success()` 才进入策略评测；失败则 `continue`（候选池 `st_seed + 20*test_num`） | `OFFICIAL_CODE_DEFAULT` | **官方代码自带**；论文未提 → 视为官方协议的一部分，但**必须记录被跳过的 seed** |
| 9 | 初始状态分布 | 同一 `setup_demo(seed)` 决定物体位姿 → 只要 seed 相同，初始状态逐位相同（已验证：同 seed 多次运行步数完全一致） | `INFERRED` | ✅ 可重复 |
| 10 | Action chunk 执行 | 论文 Eq.(3)-(5)：cue 在 chunk 内锁存，**下一个 chunk 才换指令**（chunk-preserving） | `PAPER_SPECIFIED` | ✅ 对应 `--clear-cache false`；⚠️ **runner 默认是 `true`**，必须显式覆盖 |
| 11 | 语言指令与切换 | 每任务 `instruction.segments = [s1, s2]`，长指令 `"s1, then s2"`；Oracle HSE 用 `env.subtask_completed[]` 作为 cue | `PAPER_SPECIFIED` + `OFFICIAL_CODE_DEFAULT` | ✅ |
| 12 | `sr_ordered` 计算 | `summarize_split.py`：`sr_ordered = subtask_completion.sequential["subtask_1_to_2"].rate`；
`sequential` 由 `eval_policy.py:576-593` 判定 `s1_step <= s2_step`，**不含终局夹爪条件** | `OFFICIAL_CODE_DEFAULT` | 论文 §3.1 定义 "both subtasks completed in the specified order" → 一致 |
| 13 | 训练/测试泄漏 | 训练只用 RoboTwin 原子轨迹（50 个原子任务），评测是 19 个两阶段组合 | `PAPER_SPECIFIED` | 公开仓库**不含训练代码与训练数据**，无法本地核验 → `UNKNOWN` |
| 14 | 论文未公开项 | base seed、专家筛选策略、1500 步上限、RoboTwin 具体版本、Motus checkpoint 版本与训练数据、评测机 CUDA 驱动 | — | 见 §3 |

---

## 2. 关键差异（必须先修协议再扩规模）

| # | 项目 | 论文 | 公开代码默认 | 本轮采取 | 依据 |
| --- | --- | --- | --- | --- | --- |
| D1 | episodes/任务 | 20 | **5** | **20** | 论文 §3.1 明写 380 = 19×20 |
| D2 | clear-cache | chunk-preserving | **true**（丢弃剩余 chunk） | **false** | 论文 Eq.(4)(5) + README |
| D3 | seed | 未公开 | base 42 → 4300000 | 42（并记录实际 seed） | 唯一可用的公开默认 |
| D4 | 专家筛选 | 未公开 | **开启** | 开启并逐条记录 | 官方代码行为，不关 |

**D1/D2 是本轮与 Phase 0–3A 最大差别**：之前 `full_inst` 用了 5 episodes、`oracle_hse` 用了 5 episodes，
而且 **Phase 0–3A 的 9/10、1/10 都不是 20-episode 协议下的数字**，不能作为 Table 1 的复现结论。

---

## 3. 论文未公开 / 无法核验的条件

1. **base seed 与 seed 分布**：论文只写 "20 rollouts per composition"。→ `SEED_PROTOCOL_PARITY_UNVERIFIED`
2. **专家成功筛选**：若论文未做筛选，其有效初始状态集合会包含"专家做不成"的状态，成功率会不同。
3. **每 episode 步数上限**：1500 来自官方 spec，不是论文写的。
4. **Motus checkpoint 版本**：论文引用 Motus [2]，但未给 HF 仓库名/revision。
5. **RoboTwin 版本与资产版本**：论文只引用 RoboTwin 2.0。
6. **训练数据/训练代码**：RoboCombine 公开仓库只含评测，**无训练代码**。
7. **Ordered HSE 的进度预测器**：论文附录 C.3 写 Florence 特征，公开 runner 要求 X-VLA 路径（见 `docs/15 §5`）。

---

## 4. Table 1（Motus 三列）从论文 PDF 提取的原文数值

来源：arXiv:2610.15425v1 PDF，Table 1，逐 composition 的 ordered success（%，20 rollouts/格）。

| Task | Oracle HSE | Ordered HSE | Full Inst |
| --- | ---: | ---: | ---: |
| Arrange Sign | 10.0 | 5.0 | 0 |
| Bedside | 30.0 | 25.0 | 30.0 |
| Breakfast Prep | 75.0 | 80.0 | 20.0 |
| Checkout Counter | 30.0 | 15.0 | 15.0 |
| Counter Cleanup | 15.0 | 10.0 | 15.0 |
| Desk Arrange | 10.0 | 10.0 | 5.0 |
| Hobby Desk | 35.0 | 10.0 | 15.0 |
| Living Room Tidy | 10.0 | 30.0 | 5.0 |
| Office Desk | 15.0 | 35.0 | 10.0 |
| Office Organize | 15.0 | 25.0 | 15.0 |
| Reception Desk | 15.0 | 20.0 | 5.0 |
| Stationery Sort | 10.0 | 5.0 | 10.0 |
| Store Display | 20.0 | 20.0 | 5.0 |
| Tabletop Arrange | 0 | 0 | 20.0 |
| Workspace Setup | 50.0 | 25.0 | 15.0 |
| Bakery Close | 35.0 | 10.0 | 5.0 |
| Kitchen Switch | 0 | 0 | 0 |
| Room Comfort | 0 | 0 | 0 |
| Smart Home | 0 | 5.0 | 0 |
| **Overall SR** | **19.7** | **17.4** | **10.0** |

自校验：三列逐行求和 / 19 分别 = 19.74、17.37、10.00，与论文 Overall 行吻合（说明提取无损）。

---

## 5. 结论

- **协议可复现的部分**：任务清单、指标定义、HSE 切换语义、clear-cache=false、20 episodes——都能在公开代码里实现。
- **不可核验的部分**：checkpoint 与论文模型的一致性、seed 分布、专家筛选取舍、步数上限。
- 因此本轮最高只能达到 **"Code-Reproducible but Not Fully Paper-Matched"**，除非拿到论文的 seed/checkpoint 元数据。
