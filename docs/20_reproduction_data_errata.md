# 20 · 复现数据勘误与统计修正（Gate D）

日期：2026-11-10。**所有数字从原始 `evaluation_statistics.json` / `task.log` / `_result.txt` 重新读取**，
未复制旧报告。历史原始文件一律未改动；本文件只做口径修正。

---

## 1. Checkpoint 核验（Gate B 结论）

| 项 | 值 | 证据 |
| --- | --- | --- |
| HF 仓库 | `motus-robotics/Motus_robotwin2` | hf-mirror API `/api/models/...` |
| HF repo sha | `ab74bc214f7fc5952c85198e062c5f8bf1dc47a7` | 同上（`sha` 字段） |
| HF lastModified | 2025-12-19 | 同上 |
| 发布文件 `mp_rank_00_model_states.pt` | size **16,046,580,367**；LFS `oid sha256:70bc1741b45db5e3eae86510ad3bb1bd1aef04f10b17d8c1ff4dbe099300eb65` | `/raw/main/mp_rank_00_model_states.pt`（LFS pointer） |
| 本地文件 | size **16,046,580,367**；`sha256sum` = `70bc1741…300eb65` | 服务器实测 |

→ **`PUBLIC_CHECKPOINT_PARITY_VERIFIED`**：本地权重与 HF 公开文件**逐字节一致**（size + sha256 双证）。
→ **`PAPER_CHECKPOINT_REVISION_UNVERIFIED`**：论文/仓库都未声明 Table 1 用的是哪个 revision；
   HF 仓库本身只有一个 revision（sha 固定），但**论文没写"用的就是这个"**。

伴随资源（`LOCAL_VERIFIED`，仅有大小/哈希，无官方对照）：
`Wan2.2_VAE.pth` 2,818,839,170 B；`models_t5_umt5-xxl-enc-bf16.pth` 11,361,920,418 B；
`Qwen3-VL-2B-Instruct/model.safetensors` 4,255,140,312 B，sha256 `7de1838c87a5349b…`。

---

## 2. 深跑（N=20，base 42）的准确统计

来源：`results/paper_table1/gateE_deep/**/evaluation_statistics.json`；`ordered` 按
`s1_completed ∧ s2_completed ∧ s1_step ≤ s2_step` 重算。

| Task | Track | requested | **completed** | interrupted | ordered | env | accepted seeds | exit |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| living_room_tidy | oracle_hse | 20 | **20** | 0 | **7** | 7 | 4300000–4300021 去掉 4300004、4300012 | -11（子进程） |
| office_desk | oracle_hse | 20 | **20** | 0 | **9** | 9 | 4300000–4300034 去掉 15 个 | -11 |
| living_room_tidy | full_inst | 20 | **20** | 0 | **2** | 2 | 4300000–4300019（无跳过） | -11 |
| office_desk | full_inst | 20 | **20** | 0 | **0** | 2 | 4300000–4300031 去掉 12 个 | -11 |

- office_desk / full_inst 的 2 个 env success 都是**乱序**：`4300001`（s2@359 < s1@655）、
  `4300024`（s2@45 < s1@984）→ ordered 必须是 **0，不是 2**。**（这一条已在 docs/15 正确，此处复核确认）**
- 四组深跑都跑满 20 个 completed episode，**没有截断**。`-11` 是评测后析构段错误（`docs/08 §6`）。

---

## 3. Probe（base 45，N=5 计划）的准确统计 —— **勘误**

来源：`results/paper_table1/probe/**`；"in-flight cut" 由 `task.log` 最后一条 `[Step N]` 的行号判定。

| Task | Track | requested | **completed** | in-flight cut | not started | ordered | env | exit |
| --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| breakfast_prep | oracle_hse | 5 | **5** | 0 | 0 | **5** | 5 | 124 |
| workspace_setup | oracle_hse | 5 | **5** | 0 | 0 | **5** | 5 | 124 |
| bakery_close | oracle_hse | 5 | **1** | **1（step 112 处被杀）** | 3 | **1** | **0** | 124 |
| breakfast_prep | full_inst | 5 | **3** | **1（seed 4600004，step 490 处被杀）** | 1 | **0** | 0 | 124 |
| workspace_setup | full_inst | 5 | **0** | 0 | 5 | — | — | 124 |
| bakery_close | full_inst | 5 | **0** | 0 | 5 | — | — | 124 |

### 勘误 E1（重要）：`Breakfast Prep / Full Inst` 不是 0/4

- **旧口径**（`docs/18 §8` 与 11-10 的口头汇报）：`0/4`（把第 4 个 episode 当成已完成）。
- **新口径**：**completed = 3**、env = 0、ordered = 0；第 4 个 episode（seed 4600004）在 **step 490** 被
  55 分钟外层 `timeout` 杀死，**从未完成**，**不得计入分母**；第 5 个从未开始。
- 证据：`probe/full_inst/.../breakfast_prep_2tasks/task.log` 最后一行 `[Step 490] … FAIL: S2`，
  且 `evaluation_statistics.json` 的 `episode_details` 只有 3 条（4600000/2/3）。
- 影响：`0/3 = 0%`（不是 `0/4 = 0%`）。百分比不变，**分母变了**。

### 勘误 E2：`Bakery Close / Oracle` 的 1 个样本

- 实际：**requested 5 / completed 1 / ordered 1 / env 0**。
- 该 episode（seed 4600001，s1@38、s2@135，步数 1500）是"**两子任务按序完成但终局夹爪不达标**"，
  所以 `ordered=1` 而 `env_success=0`。这不是矛盾，是 `sr_ordered` 与 `env success` 的定义差（`docs/19` 度量行）。
- 第 2 个 episode 在 **step 112** 被杀，**不计**。后 3 个未开始。

### 勘误 E3：`Workspace Setup / Full Inst`

- 无 `tasks/workspace_setup_2tasks/` 目录 → **`N=0 / NOT_RUN`**，不是 "0/5 失败"。
- `docs/18 §8` 写作 "0/5（未开始）" 容易误读为失败 5 次，此处明确为 `NOT_RUN`。

### 勘误 E4：本轮新增 rollout 计数

- 旧：口头报 "oracle 11 + full 4 = 15"。
- 新：**completed = 14**（oracle 11 + full 3），另有 **2 个 in-flight 被杀**、**9 个从未开始**。
  预算上限 30 次，**实际完成 14 次**，未超限。

---

## 4. 另一个已确认的记录缺陷（非本轮引入）

`eval_policy.py` 在**复用同一个 `save_dir`** 时，`total_successes` 取 `len(successful_seeds)`（累计文件），
而 `total_episodes` 只统计本进程 → 曾出现 `eps=2 succ=3` 的不自洽（Phase 3 office_organize）。

- 影响范围：`results/phase3/gateD/office_organize_*`（历史目录，**不修改**）。
- 本轮 Phase 4 的每个 invocation 都用**独立目录**，四组深跑与三次 probe **未受影响**。
- 结论：**统计必须以 `episode_details` 为准，不能直接用 `metadata.total_successes`**。
  `scripts/check_paper_reproduction.py` 已按此实现（重算 ordered / 校验 ep 数）。

---

## 5. 复核清单（逐项）

| 检查 | 结果 |
| --- | --- |
| `docs/15` 四组 N=20 数字 | ✅ 与原始 stats 一致（7/20、9/20、2/20、0/20 ordered） |
| `docs/15` "两任务均值" 12.5% / 7.5% | ✅ 算术正确（(10+15)/2、(5+10)/2） |
| `docs/16` "35% 是论文 10% 的 3.5 倍" | ✅ |
| `docs/18` 深跑 seed 清单 | ✅ 见 §2 |
| `docs/18` probe 的 5/5, 5/5, 1/5 | ✅ 但 bakery 需按 §3 口径写（completed=1） |
| `docs/18` "25.7% / 31.8%" | ✅ 已标注为**反事实估计**，本轮再次确认不可当结果 |
| 历史原始文件是否被改动 | ❌ 未改动（`results/paper_table1/**` 只新增，不覆盖） |
