# 19 · 官方协议逐项对照（Gate A）

日期：2026-11-10。证据来源：官方仓库 `df237b2`（本地 `third_party/RoboCombine`）、HF 模型卡/API、
本地原始统计与日志。标签可组合。

**官方仓库 HEAD 核验**：GitHub API `repos/AutoLab-SAI-SJTU/RoboCombine/commits` 返回
首条 sha = `df237b22bd5c39d705b103daf2b9a8a168c9d453`（2026-10-15 "docs: add paper authors below README title (#7)"）
→ 与本地 checkout **完全一致**，**官方自 2026-10-15 起没有新提交**。
（`LOCAL_VERIFIED` + `OFFICIAL_CODE_SPECIFIED`）

本地 `third_party/RoboCombine` 工作区与 `df237b2` 的**内容差异为 0 行**（`git diff --ignore-cr-at-eol --numstat` 全 0，
只有 13 个文件因 Windows CRLF 显示为 modified）→ **本地 clone 是纯净官方代码**。
（`LOCAL_VERIFIED`）

---

## 1. 逐项对照表

| 配置项 | 论文（P） | 官方当前代码（O） | 本地实际（L） | 判定 |
| --- | --- | --- | --- | --- |
| Task split | 19 个两阶段组合（§3.1 "19 novel multi-stage compositions"） | `handoff_eval/specs/robocombine.json` `tasks` 数组 19 项，`stage_count=2`，含 `instruction.segments` 与 `long` | 同一份 spec（hash `7998f1850bccbb6e…`），19 任务 | `PAPER_SPECIFIED`+`OFFICIAL_CODE_SPECIFIED`+`LOCAL_VERIFIED` |
| Track | 三种：Oracle-HSE / Ordered-HSE / Full-Inst（Table 1 列名） | `--track {full_inst,oracle_hse,ordered_hse}`（run_split:41） | 只跑 `full_inst`、`oracle_hse` | `PAPER_SPECIFIED`+`OFFICIAL_CODE_SPECIFIED`+`LOCAL_VERIFIED`；`ordered_hse` 未跑（见 `docs/15 §4`） |
| Episodes | **20/任务**，380=19×20（§3.1） | spec `default_episodes: 5`；README:114 "default episodes: `5`"；`run_split.py:146` 未指定时取 spec 默认 | 深跑显式 `--episodes 20`；预检 3 | `PAPER_SPECIFIED`+`OFFICIAL_CODE_SPECIFIED`；**本地覆盖为 20**（`LOCAL_VERIFIED`） |
| Max steps | 论文**未写** | spec `default_max_steps_per_episode: 1500`；`run_split` 透传 `--max-steps-per-episode` | 1500 | `OFFICIAL_CODE_SPECIFIED`+`LOCAL_VERIFIED`；**论文一致 → `UNVERIFIED`** |
| Initial seed | 论文**未公开** | `--base-seed` 默认 42；`run_split:147` 传 `--seed <base_seed>`；spec 无 `seed_receipt` | base 42 → `st_seed=4300000`；probe 用 45 → 4600000 | `OFFICIAL_CODE_SPECIFIED`+`LOCAL_VERIFIED`；**论文一致 → `UNVERIFIED`** |
| Seed 换算 | — | `st_seed = 100000*(1+base_seed)`（Phase 1 实测：base 42→4300000、45→4600000） | 一致 | `LOCAL_VERIFIED` |
| Seed sampling | — | `eval_policy.py:761-762`：priority seeds + `range(st_seed, st_seed+test_num*20)` | 无 priority 文件时即 range 顺序 | `OFFICIAL_CODE_SPECIFIED`+`LOCAL_VERIFIED` |
| Expert screening | 论文**未提** | `eval_policy.py:775-790`：先跑专家 `play_once()`，`not (plan_success and check_success())` → `continue`（**不计数**） | 默认启用，观察到的跳过见 `docs/20 §2` | `OFFICIAL_CODE_SPECIFIED`+`LOCAL_VERIFIED`；论文是否相同 `UNVERIFIED` |
| Success skipping | 论文**未提** | `skip_successful=True`（713），`successful_seeds` 来自 `*_successful_seeds.json`（722-723），`test_num`/`suc` 续接（731-732） | 每次 invocation 独立目录，未跨 run 续跑；同一目录内 `successful_seeds` 会累计（Phase 4 曾出现 `eps=2 succ=3`，见 `docs/20 §4`） | `OFFICIAL_CODE_SPECIFIED`+`LOCAL_VERIFIED` |
| Scene config | "clean"未明说 | `task_config/robocombine_eval.yml`：`random_background:false`、`cluttered_table:false`、`clean_background_rate:1`、`random_head_camera_dis:0`、`random_table_height:0`、`random_light:false` | 同一份 yml（hash `e5210bbb89fb5f40…`） | `OFFICIAL_CODE_SPECIFIED`+`LOCAL_VERIFIED`；论文一致 `UNVERIFIED` |
| Model | Motus [2] | README 只说"提供自己的 checkpoint"，仓库不含权重 | `Motus_robotwin2`（HF `motus-robotics/Motus_robotwin2`，repo sha `ab74bc214f7f…`）；权重 sha256 `70bc1741…` **= HF LFS oid** | `PUBLIC_CHECKPOINT_PARITY_VERIFIED`（`docs/20 §1`）；论文 revision `PAPER_CHECKPOINT_REVISION_UNVERIFIED` |
| Action chunks | chunk-preserving（Eq.4-5：cue 在 chunk 内锁存，下个 chunk 才换指令） | README:288-292 明写：默认 `--clear-cache true` 丢弃剩余动作，**论文设置用 `--clear-cache false`**；`run_split:55` 默认 `'true'`，`:148` 透传 | 全程 `--clear-cache false` | `PAPER_SPECIFIED`+`OFFICIAL_CODE_SPECIFIED`+`LOCAL_VERIFIED`；**若用默认 true 则 `MISMATCH`** |
| Chunk 执行机制 | 同上 | `policy/Motus/deploy_policy.py:42` `action_cache=deque()`；`:68-75` `prepare_instruction_switch(clear_action_cache)`；`:305-315` 优先 `popleft()` 复用缓存 | 实测：cue=51 → switch=64，缓存 13→0（Phase 2 Gate D） | `OFFICIAL_CODE_SPECIFIED`+`LOCAL_VERIFIED` |
| HSE 时序 | cue 锁存、下一 chunk 生效 | `handoff_eval/hse.py:45-58` `apply_instruction_switch`；`:177-184` `flush_pending_switch` **仅当 `len(action_cache)==0`** 才真正切换；`:186+` `handle_oracle_hse` 用 `env.subtask_completed` 作 cue | cue≠switch 已实测（Δt=1–39 步） | `PAPER_SPECIFIED`+`OFFICIAL_CODE_SPECIFIED`+`LOCAL_VERIFIED` |
| Metrics | SR_ord = 两阶段**按序**完成；另有 SR1/SR2/Conv | `summarize_split.py:38-55`：`sr_ordered = subtask_completion.sequential["subtask_1_to_2"].rate`；`eval_policy.py:576-593` 判 `s1_step<=s2_step`（**不含夹爪**）；episode success 另算 | 同步报告 env success 与 sr_ordered | `PAPER_SPECIFIED`+`OFFICIAL_CODE_SPECIFIED`+`LOCAL_VERIFIED` |
| Runtime | 未写 | `docs/runtime_envs.md`：Motus 用 Python 3.10 的独立环境 | Python 3.10.21 / torch 2.4.1+cu121 / SAPIEN 3.0.0b1 / mplib 0.2.1 / CuRobo 0.7.6 | `OFFICIAL_CODE_SPECIFIED`+`LOCAL_VERIFIED`；论文一致 `UNVERIFIED` |
| Artifacts | 未写 | `run_split` 写 `run_manifest.json`、`summary.json/md`、`used_seed_receipts/<task>.txt`；`eval_policy` 写 `evaluation_statistics.json`、`*_expert_demo_seeds.json`、`*_successful_seeds.json`、`task.log`、`_result.txt` | 全部存在（`results/paper_table1/**`） | `OFFICIAL_CODE_SPECIFIED`+`LOCAL_VERIFIED` |

---

## 2. `--clear-cache false` 的端到端核验（逐级穿透）

| 层 | 证据 | 结论 |
| --- | --- | --- |
| README | L288-292："Use `--clear-cache true` (default)… or `--clear-cache false`… **For the paper's chunk-preserving setting, select `--clear-cache false` explicitly.**" | 论文该设置**必须显式传** |
| runner CLI | `run_split.py:55` `default='true'` | 不传就是 **true** → 与论文相反 |
| runner → eval | `run_split.py:148` `overrides.extend(['--clear_cache', str(getattr(args,'clear_cache','true'))])` | 显式传递 |
| eval CLI | `eval_policy.py:1017` `--clear_cache type=parse_clear_cache`；`:1050` 默认取 config | 可覆盖 |
| HSE 语义 | `hse.py:45-58` → `model.prepare_instruction_switch(clear_action_cache=False)` | 不清缓存 |
| 策略侧 | `deploy_policy.py:68-75` 只在 `clear_action_cache=True` 时 `.clear()` | false 时保留 |
| 切换时机 | `hse.py:177-184` 仅当 `len(action_cache)==0` 才 `flush_pending_switch` | **真正的"排空后才切"** |
| 运行记录 | 所有 Phase 4 命令 `--clear-cache false`（`results/paper_table1/**/command.sh`） | `LOCAL_VERIFIED` |

→ **本地的 chunk-preserving 语义与论文一致**；若误用 runner 默认 `true`，会得到 `MISMATCH`。

---

## 3. 本地对官方代码的改动（`third_party/RoboCombine`，服务器工作区）

`git diff --stat`：**3 个文件，32 行新增 / 3 行删除**；外加 2 个**新增未跟踪文件**。

| 文件 | 改动 | 是否影响动作/初始化/切换/判据 |
| --- | --- | --- |
| `envs/camera/camera.py` | `import open3d` 改为 try/except（缺库不崩） | **否**（只影响导入） |
| `policy/Motus/deploy_policy.py` | 保留 `sys.stdout/stderr` 引用，避免 GC 后 `print` 抛 `OSError` | **否**（只影响日志） |
| `script/eval_policy.py` | 新增 `shb_trace.hook(...)` 调用 8 处；未设 `SHB_TRACE_JSONL` 时 `hook()` 立即 return | **否**（纯旁路；已用 A/B 三跑验证动作逐位一致，`docs/08 §5`） |
| `envs/place_phone_stand.py`、`envs/stamp_seal.py` | Phase 3 新增的**原子任务** env（不在 19 任务 spec 内） | **否**（19 任务评测不会加载） |

**没有任何改动触及**：`_base_task.setup_demo`、seed 生成、专家筛选、`check_success`、`sr_ordered` 计算、chunk 长度。
（`LOCAL_VERIFIED`，diff 可复核）

---

## 4. 三条明确结论

1. **官方代码自 2026-10-15 未变**，本地用的就是当前 HEAD。
2. **官方默认值不能直接当论文设置**：episodes 默认 5（论文 20）、clear-cache 默认 true（论文 false）。
   这两项本地方向都正确（20 / false），且都在命令里显式写出（`command.sh` 可查）。
3. **论文未公开部分**（base seed、专家筛选用法、步数上限、checkpoint revision、RoboTwin 版本）
   仍为 `UNVERIFIED`，不得用官方默认值冒充。
