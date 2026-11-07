# 05 · 复现协议核验审计（Gate A）

审计时间：2026-11-07 09:30–10:10 CST。**审计对象是本地真实文件与服务器原始日志，不是上一轮报告的口述。**
凡未能核实的项，明确写 `UNVERIFIED`，不推测。

> 网络状态说明：审计开始时 `222.29.51.96:22` 不可达（VPN 断开），因此本文件**只用本地仓库里已有的
> 原始产物**（`results/*/official/` 是从服务器拷回的完整官方输出）完成核验；服务器端复核命令见 §9，
> 恢复网络后可直接跑一遍比对。

---

## 0. 结论摘要

| 问题 | 结论 |
| --- | --- |
| 两个提交是否存在 | ✅ `2216554`、`868de83` 都在 `main` 上 |
| 为什么 GitHub 还是旧的 Phase 0 README | ✅ **两个提交从未 push**：`origin/main = 8bd6092`，本地 `ahead 2 / behind 0` |
| 10 次 rollout 是否真实 | ✅ 有逐 episode 的 `task.log` + `evaluation_statistics.json`，seed/步数/切换步齐全 |
| Gate 2 是否与 Gate 3 重复计数 | ⚠️ **是**：Gate 2 的 `living_room/seed 4300000` 与 Gate 3a 的第 1 个 episode **数值完全相同**（173 步 / s1@51 / switch@64）→ **唯一 rollout = 10，不是 11** |
| 是否有"重试到成功" | ❌ 未发现：两次运行各 5 episode，`task.log` 里 `setup_demo` 恰好 10 次（每 episode 1 次专家校验 + 1 次策略），`expert_demo_seeds.json` 恰好 5 个 seed，无额外 seed |
| 与论文 10% / 15% 的差距 | ⚠️ **不是同一 evaluation setting**：我们的协议至少有 4 处可证差异（clean 场景 / 1500 步预算 / 运行时专家筛种 / chunk-preserving 切换），且 checkpoint 与论文的对应关系 `UNVERIFIED` |
| 7 个协议项的判定 | 见 §5（4 项可证不同、2 项部分不同、1 项未变） |
| 审计结论 | **PARTIAL**：结果真实、可复现，但**不能声称复现论文 Table 1**；应命名为 "RoboCombine oracle_hse · clean · 1500-step · expert-filtered-seed" |

---

## 1. 仓库与提交核验

```text
$ git rev-parse HEAD
868de8369aa44362db6d27f479ca61bb9fd231f5
$ git --no-pager log --oneline -3
868de83 docs/04: add red-line self-check with server-verified evidence
2216554 Phase 0C audit + Phase 1 baseline: Motus+oracle_hse real rollout (Gate 1/2/3 pass)
8bd6092 记录 checkpoint 清理：…（Phase 0）
$ git branch -vv
* main 868de83 [origin/main: ahead 2]
$ git rev-list --left-right --count origin/main...HEAD
0	2
$ git --no-pager log origin/main --oneline -2
8bd6092 记录 checkpoint 清理：…
1ca7ba8 初始化 SkillHandoffBench：…
```

**判定**
- 两个提交**确实存在且在当前分支**：`git cat-file -t` 对两者都返回 `commit`。
- 公开 GitHub 显示旧 README 的原因**不是**提交丢了，而是**从未 push**：`origin/main` 仍停在 `8bd6092`，
  本地领先 2 个提交。本轮遵守"未审查敏感配置前不自动推送"，因此**仍然没有 push**。
- 敏感信息检查（push 前置条件）：
  - `git ls-files` 中无 `*.local.env` / `*.key` / `*.pem` / `secret*`；
  - `git grep <服务器口令>` → **无命中**（口令本身不写进文档，只在被 gitignore 的 `configs/resources.local.env`）；
  - `git check-ignore -v configs/resources.local.env` → `.gitignore:42:*.local.env` 命中；
  - 受跟踪文件 83 个，无 >1 MB 文件。

---

## 2. 10 次 rollout 的原始证据

来源：`results/<run>/official/tasks/<task>/` 下的 `task.log`、`evaluation_statistics.json`、
`command.sh`、`*_expert_demo_seeds.json`、`*_successful_seeds.json`。

### 2.1 `living_room_tidy_2tasks`（5 episodes，run `20261107_012314`）

| # | seed | 成功 | 总步数 | s1 完成步 | s2 完成步 | cue 步 | switch 步 | cue→switch |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 4300000 | ✅ | 173 | 51 | 125 | 51 | 64 | 13 |
| 2 | 4300001 | ✅ | 253 | 51 | 102 | 51 | 64 | 13 |
| 3 | 4300002 | ✅ | 465 | 51 | 102 | 51 | 64 | 13 |
| 4 | 4300003 | ✅ | 174 | 47 | 160 | 47 | 48 | 1 |
| 5 | 4300004 | ✅ | 159 | 50 | 128 | 50 | 64 | 14 |

### 2.2 `office_desk_2tasks`（5 episodes，run `20261107_013845`）

| # | seed | 成功 | 总步数 | s1 完成步 | s2 完成步 | cue 步 | switch 步 | cue→switch |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 4300000 | ✅ | 172 | 43 | 168 | 43 | 48 | 5 |
| 2 | 4300001 | ✅ | 285 | 79 | 246 | 79 | 80 | 1 |
| 3 | 4300002 | ✅ | 423 | 44 | 400 | 44 | 48 | 4 |
| 4 | 4300003 | ❌ | **1500** | 177 | — | 177 | 192 | 15 |
| 5 | 4300004 | ✅ | 206 | 49 | 201 | 49 | 64 | 15 |

### 2.3 失败的那个 episode 的证据链（`office_desk` seed 4300003）

- `evaluation_statistics.json`：`success=False, total_steps=1500, s1_completed=True, s2_completed=False`，
  `failure_analysis.by_type.timeout.count = 1`；
- `task.log` 末尾（1500 步触顶）：

  ```
  [Step 1497] S1:✓ S2:✗ L:0.070(✗) R:1.000(✓) -> FAIL: S2
  [Step 1498] S1:✓ S2:✗ L:0.280(✗) R:1.000(✓) -> FAIL: S2
  [Step 1499] S1:✓ S2:✗ L:0.537(✗) R:1.000(✓) -> FAIL: S2
  ```

- **这是"第一阶段成功、切换也发生、但下游没完成"的案例**（s1@177，switch@192，之后 1308 步无第二阶段完成）。

---

## 3. 去重：Gate 2 与 Gate 3 的关系

| 项 | Gate 2（`20261107_010606`） | Gate 3a 第 1 个 episode（`20261107_012314`） |
| --- | --- | --- |
| task | living_room_tidy_2tasks | 同 |
| seed | 4300000 | 同 |
| 总步数 | 173 | 173 |
| s1 / s2 | 51 / 125 | 51 / 125 |
| cue / switch | 51 / 64 | 51 / 64 |

→ **完全相同**，是同一初始状态 + 确定性推理的重复运行。

- **唯一 rollout 数 = 10**（living 5 + office 5）。
- Gate 2 的作用只是"首次跑通证明"，**不计入 Gate 3 的 10 次**，也不单独作为第 11 个样本。
- 顺带得到一个额外证据：**同 seed 重复运行的结果逐位相同**（步数、完成步、切换步全部一致），
  说明 Motus 推理在本配置下是**确定性**的 —— 这对 Gate D 的"启用/停用日志是否改变结果"检验很关键。

---

## 4. 是否存在"失败重试后只保留成功"

### 4.1 计数证据

| run | task | `setup_demo` 次数 | 专家 demo 成功次数 | expert_demo_seeds | episodes |
| --- | --- | --- | --- | --- | --- |
| Gate 3a | living_room | **10** | 5 | 4300000–4300004（5 个） | 5 |
| Gate 3b | office_desk | **10** | 5 | 4300000–4300004（5 个） | 5 |

- 10 次 setup = 5 个 seed ×（1 次专家校验 + 1 次策略执行），**没有多余的 seed 尝试**。
- `*_expert_demo_seeds.json` 里的 seed 与 `episode_details[].seed` **一一对应**。
- 若某个 seed 的专家 demo 失败，代码会 `continue` 到下一个 seed（`eval_policy.py:786-788`），
  此时 setup 次数会 > 10、expert seeds 会少于 episode 数。**本数据没有发生这种情况。**

### 4.2 但必须点明：**seed 是"专家可解"筛过的**

`eval_policy.py:780-789`：

```python
task_env.setup_demo(...)
episode_info = task_env.play_once()      # 官方专家脚本
task_env.close_env()
if not (task_env.plan_success and task_env.check_success()):
    continue                              # 专家都做不成的初始状态直接跳过
```

这是**官方 RoboTwin 评测协议的一部分**（不是我们加的），但它意味着：
> 所有被计入的初始状态，都至少"脚本专家能完成"。

因此这不是"随机初始状态上的成功率"，而是"专家可解初始状态上的成功率"。
论文若采用同样的协议，此项不构成差异；若论文用的是 seed receipt（预先固定的 seed 列表），
则两者仍然等价（receipt 也是筛过的）。**这一点无法在无网络条件下核实论文，记 `UNVERIFIED`。**

### 4.3 `successful_seeds.json` 里的异常值（官方代码的 bug，非我们篡改）

```
"total_tested": 4, "success_rate": 1.25
```

`save_successful_seeds(...)` 在 `task_env.test_num += 1` **之前**被调用（`eval_policy.py:959-960` vs `:974`），
所以 `total_tested` 少 1、`success_rate` 可以 >1。这是**上游代码的记账 bug**，
但它恰好证明我们**没有**为了好看去改这些文件（否则不会留下 1.25 这种数）。

---

## 5. 与论文 Table 1 的逐项比对（用户给的论文值：Living Room 10%、Office Desk 15%）

| # | 协议项 | 论文（用户转述） | 我们的实际配置 | 证据 | 判定 |
| --- | --- | --- | --- | --- | --- |
| 1 | `priority_seeds_file` | 推测：用预先固定的 seed receipt | **未使用**（spec 里没有任何 `seed_receipt` 字段；`run_split.py:110-117` 返回 `None`） | `handoff_eval/specs/robocombine.json`（全文无 `seed` 键）、`command.sh` | **不同**（我们靠运行时专家筛种） |
| 2 | Expert demo seeds / successful seeds 来源 | 未知 | 每个 seed 先跑官方 `play_once()`，失败即跳过；本轮 5/5 一次通过 | `task.log`（10 次 setup）、`*_expert_demo_seeds.json` | **协议内建**，非我们添加 |
| 3 | 是否使用"筛选过的初始化种子" | 未知 | **是**：只保留专家可解的 seed（官方行为） | 同 #2 | **是**（需论文确认是否相同） |
| 4 | `robocombine_eval` 场景配置 | 未知 | **全 clean**：`random_background: false`、`cluttered_table: false`、`random_light: false`、`random_table_height: 0`、`random_head_camera_dis: 0`、`clean_background_rate: 1` | `task_config/robocombine_eval.yml:7-14` | **很可能不同**（论文大概率含 randomized） |
| 5 | 最大步数 / episode 数 | 未知（spec 默认 5 / 1500） | `--episodes 5`、`--max-steps-per-episode 1500`；两个组合任务**不在** `_eval_step_limit.yml` 里 → 默认 1000 被覆盖成 1500 | `_base_task.py:116-122`、`eval_policy.py:64-74`、`task.log` 的 `override: 1000 -> 1500` | **不确定**（若论文用官方 per-task 限额会更难） |
| 6 | `--clear-cache false` 的行为 | 论文的 chunk-preserving 设置 | 已固定 `false`，并**观测到延迟切换**（cue→switch 1–15 步） | `hse.py:136-144`；10/10 episode 的 `cue_step < switch_step` | **一致**（但这本身会提高成功率） |
| 7 | 真实 Motus checkpoint 与论文配置的对应 | 未知 | `Motus_robotwin2`（16.05 GB，sha256 `70bc1741…`），官方 HF 的 RoboTwin2 微调版 | `run_manifest.json`、`docs/03 §2.1` | `UNVERIFIED`：论文 Table 1 是否用同一权重无法核实 |
| 8 | 是否修改官方 task success 判据 | 不应修改 | **未修改**：只有 2 个运行性 patch（open3d 可选、stdout 保活），`check_success()` 一行没动 | `docs/patches/*.diff`、`git diff` in `third_party/RoboCombine` | **未修改** ✅ |

### 5.1 结论

> 我们跑的是 **"RoboCombine `oracle_hse` · clean 场景 · 1500 步预算 · 运行时专家筛种 · chunk-preserving"**。
> 这**不等于**论文 Table 1 的 evaluation setting。**不得**把 9/10 或 5/5 声称为"复现论文 10%/15%"。

---

## 6. 差距是不是采样噪声？

| 任务 | 我们的 k/n | Wilson 95% CI | 论文值 | 论文值在 CI 内？ |
| --- | --- | --- | --- | --- |
| living_room_tidy_2tasks | 5/5 | [0.566, 1.000] | 10% | **否** |
| office_desk_2tasks | 4/5 | [0.376, 0.964] | 15% | **否** |
| 合并 | 9/10 | [0.596, 0.982] | — | — |

→ **不是小样本波动**：n=5 时即使最保守的区间下界也有 57.7%，远高于 10–15%。
差距必须由**协议/资产/权重**差异解释，不能归因于"运气好"。

---

## 7. 差距的候选解释（按证据强度排序）

| 排序 | 假设 | 支持证据 | 反对/未验证 | 如何判定（下一轮） |
| --- | --- | --- | --- | --- |
| **H1** | **clean vs randomized 场景**：`robocombine_eval` 关掉了全部域随机化 | 配置文件逐项为 false；RoboTwin 官方"s 强域随机化"是卖点 | Motus 单任务 clean 88.66% vs randomized 87.02%，差异很小 → 单独不足以造成 10x | 用 `demo_randomized` 等价配置跑同一任务 1×5（需新增 5 次 rollout） |
| **H2** | **步数预算 1500 vs 官方 per-task 限额** | 组合任务不在 `_eval_step_limit.yml`，默认 1000 被覆盖为 1500；失败案例正好吃满 1500 步 | 官方 spec 默认就是 1500 | 用 400/900 步预算跑同任务，看成功率是否塌陷 |
| **H3** | **checkpoint 不同**：论文可能用更弱的 Motus（stage-2 base）或不同微调版 | 我们用的是 RoboTwin2 专用微调版（最强）；论文没写清 | 无法核实 | 论文/作者确认权重名与 sha256 |
| **H4** | **chunk-preserving（`clear-cache false`）+ 分阶段指令**让任务变简单 | cue→switch 延迟 1–15 步，等于给旧指令更多执行时间 | 论文把 `false` 称为自己的设置 | 用 `--clear-cache true` 跑一组对照（5 次） |
| **H5** | **成功判据版本**：论文可能用了更严格的接触/顺序判据 | 我们未改判据；官方 compound 判据是"全子任务完成 + 夹爪张开" | 无证据表明论文更严 | 读论文附录/代码，逐条比 `check_success` |
| **H6** | 任务实现版本不同（envs 被改过） | 我们用的是官方 commit `df237b2` | 论文可能基于内部版本 | 与作者核对 commit/任务文件 hash |

**最可能的主因**：H1 + H2 的组合（更难的场景 + 更紧的预算），
其次是 H3（权重不同）。这三项都能用**新增 ≤15 次 rollout** 做判定，已列入下一轮计划。

---

## 8. 本次审计暴露的两个"日志陷阱"（对 Gate D 很重要）

1. **`Oracle HSE -> stage 2 at step N` 这行在 `--clear-cache false` 下几乎不会打印。**
   原因：`hse.py:136-144` 在 `action_cache` 非空时把切换**挂起**（`pending_switch`），
   真正的切换由 `flush_pending_switch()` 完成，而它**不打印**。
   实测：5 个 episode 的 `task.log` 里 `Oracle HSE ->` 出现 **0 次**，但 `switch_events` 有 5 条。
   → **不能用日志里有没有这行来判断是否切换**；必须读 `evaluation_statistics.json`。

2. **最后一行 `FAIL` 不代表 episode 失败。**
   `take_action()` 在**一个 action 内**会 `scene.step()` 多次并每次调用 `check_success()`
   （`_base_task.py:1395-1413`），而日志按 `take_action_cnt` 去重打印。
   例：living_room seed 4300004 的末行是 `[Step 159] … FAIL: L<0.8`，但该 episode 的
   `success=True, total_steps=159` —— 因为成功发生在**同一步编号的后续物理子步**里。
   → **终局判定只能以 `evaluation_statistics.json` / `eval_success` 为准。**

这两条直接决定 Gate D 的采样点设计：**必须记录 `take_action_cnt` + 子步计数**，
并且**不能**把"cue 行"与"switch 行"当成同一事件。

### 8.1 附带的取证发现（Phase 1 数据的失败 episode，`scripts/forensics_episode.py`）

对 `office_desk_2tasks` 的 5 个 episode 做行为形态统计（只读 `task.log`，不重跑）：

| ep | seed | 成功 | S1 首次完成 | S2 首次完成 | 最长 (S1,S2) 平台 | 平台长度 |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 4300000 | ✅ | step 44 | step 169 | (True, False) | 125 |
| 1 | 4300001 | ✅ | step 80 | step 247 | (True, False) | 167 |
| 2 | 4300002 | ✅ | step 45 | step 401 | (True, False) | 356 |
| **3** | **4300003** | ❌ | **step 178** | **从未** | **(True, False)** | **1323** |
| 4 | 4300004 | ✅ | step 50 | step 202 | (True, False) | 152 |

- 成功 episode 的第二阶段平台长度 125–356 步；失败的这一条是 **1323 步且从未达成**。
- 也就是说：**第一阶段成功、切换发生（192）之后，机器人在第二阶段停留了 1308 步而毫无进展**。
  这个形态**既可能是"交接状态不适合下游"**，也可能是"下游技能本身在这个构型下做不到"——
  **仅凭日志无法区分**（这正是 Gate D 要解决的问题）。
- 另一个细节：日志里 `[Step 44]` 与 JSON 里的 `s1_step=43` 差 1 —— 因为日志是在动作执行后打印的。
  **Gate D 的时间戳一律以 `take_action_cnt` 为准，并记录它是"动作前"还是"动作后"的快照。**

---

## 9. 网络恢复后的服务器复核命令（本轮未执行）

```bash
# 1) 提交是否与本地一致
cd /scratch/lijh/SkillHandoffBench && ls docs results

# 2) 10 次 rollout 的原始统计（与 §2 表逐项比对）
python3 - <<'EOF'
import json, glob
for p in sorted(glob.glob('/scratch/lijh/SkillHandoffBench/results/gate3*/official/tasks/*/evaluation_statistics.json')):
    d = json.load(open(p)); m = d['metadata']
    print(p.split('/tasks/')[-1], m['total_episodes'], m['total_successes'])
    for e in d['episode_details']:
        print('  ', e['seed'], e['success'], e['total_steps'], e['s1_step'], e['s2_step'], e.get('switch_step'))
EOF

# 3) 确认没有重试/筛选：setup 次数应 == 2 × episodes
grep -c "not in step limit file" /scratch/lijh/SkillHandoffBench/results/gate3*/official/tasks/*/task.log

# 4) 确认判据未被改：仓库内 git diff 只有 2 个 patch
cd /scratch/lijh/SkillHandoffBench/third_party/RoboCombine && git status --short && git diff --stat
```

---

## 10. 审计结论

| 维度 | 判定 |
| --- | --- |
| 结果真实性 | **PASS**：逐 episode 原始日志/JSON/种子齐全，同 seed 重跑逐位一致 |
| 计数正确性 | **PASS（已修正）**：唯一 rollout = 10，Gate 2 不计入 |
| 无"重试到成功" | **PASS**：setup 次数与 seed 列表一一对应 |
| 判据未被篡改 | **PASS**：2 个 patch 均为运行性修复 |
| 与论文协议一致 | **FAIL**：至少 4 项可证差异（clean、1500 步、运行时筛种、chunk-preserving） |
| 与论文数字可比 | **不可比**：Wilson CI 下界 0.566 ≫ 0.10 |

> **Gate A 判定：`PARTIAL`。**
> 结果真实可用、可作为**我们自己定义的 setting** 的基线，
> 但**不能**被称为"复现论文 Table 1"；后续所有报告必须使用完整 setting 名称。
