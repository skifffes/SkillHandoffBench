# 03 · 执行报告（真实命令、seed、耗时、日志路径）

> 本文件只写**实际发生的事**。所有数字都有对应的日志/文件路径，可复查。
> 机器：`222.29.51.96`（用户 `lijh`），GPU 0（A40 48 GB），CentOS 7.9 / glibc 2.17 / driver 550.120。
> 时间均为服务器本地时间（CST）。

---

## 1. 时间线

| 时间 | 事件 | 证据 |
| --- | --- | --- |
| 22:54 | SSH 连通；磁盘 232 GB；5×A40 空闲；GitHub 可达、HF 直连不可达 | `docs/01 §5` |
| 22:58 | clone RoboCombine → `df237b2` | `third_party/RoboCombine` |
| 23:03 | 资产下载启动 | `logs/fetch_assets.log` |
| 23:07 | clone Motus 源码（仅参考，不进运行时） | `third_party/Motus-src` |
| 23:08 | 建 Motus venv（v1，失败） | `logs/setup_motus_env.log` |
| 23:20 | 改为关键路径下载队列（发现镜像不支持 Range 续传） | `logs/fetch_priority.log` |
| 23:33 | venv v2（修正 torch 索引 / 依赖 pin / numpy / diffusers） | `logs/setup_v2.log` |
| 23:47 | 资产 3 个 zip 全部下载完成（14.93 GB）并解包 | `third_party/RoboCombine/assets/{objects,embodiments,background_texture}` |
| 23:52 | 补齐 X11 运行库（RPM 解包）、Vulkan loader、opencv-headless | `logs/fix_env.log`、`scripts/setup_x11.sh` |
| 23:55 | **Gate 1** 跑通（19 任务 / 38 pytest / import / 渲染） | `logs/gate1.log` |
| 00:00 | 权重全部到位：Motus 16.05 GB、Wan2.2 子集 14.20 GB、Qwen3-VL 4.27 GB | `assets/models/*` |
| 00:02–00:50 | 构建 CuRobo v0.7.6（nvcc 由 micromamba 提供，8 轮增量重试） | `logs/curobo_retry_outer.log` |
| 00:53 | **仿真栈 smoke 通过**：建场景 + 专家 demo 双阶段成功 | `logs/sim_smoke.log` |
| 00:57 | Gate 2 第一次尝试：pytorch3d/stdout 问题（已打 patch 002/003） | `results/_official/.../20261107_005734/` |
| 01:06–01:16 | **Gate 2 通过**：Motus + oracle_hse 真实 rollout，1/1 成功 | `results/gate2_20261107_010606_*` |
| 01:17 | 启动 Gate 3（2 任务 × 5 episodes） | `logs/gate3*.log` |

---

## 2. Gate 1：CPU / 运行时检查（PASS）

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| `run_split.py --list-tasks` | **19** 个任务 | `logs/gate1.log`（`GATE 1-a`） |
| `pytest tests/test_language_switch_runtime.py` | **38 passed in 2.43s**（无需 GPU / checkpoint） | 同上 `GATE 1-b` |
| 最小依赖 import | numpy 1.26.4 / torch 2.4.1+cu121 / sapien 3.0.0b1 / mplib 0.2.1 / toppra / transforms3d 0.4.2 / h5py 3.11.0 / cv2 4.10.0 / transformers 5.0.0rc0 / diffusers 0.31.0 全 OK；`import envs` OK | 同上 `GATE 1-c` |
| checkpoint sha256 | `70bc1741b45db5e3eae86510ad3bb1bd1aef04f10b17d8c1ff4dbe099300eb65`，**16,046,580,367 B** | `docs/03 §2.1` |
| GPU | `0, NVIDIA A40, 46068 MiB`，单卡 | `GATE 1-e` |
| SAPIEN 渲染（Vulkan 关键检查） | `RENDER OK (48, 64, 3) float32 mean=0.73` | `GATE 1-f` |

### 2.1 checkpoint 完整性

```
size   16046580367
sha256 70bc1741b45db5e3eae86510ad3bb1bd1aef04f10b17d8c1ff4dbe099300eb65
path   assets/models/Motus_robotwin2/mp_rank_00_model_states.pt
```

（HF 只提供 LFS 指针，没有发布官方 sha256，因此这里是**本地计算的指纹**，用于后续复现比对，不宣称与官方一致。）

### 2.2 仿真栈 smoke（不算评测成绩）

`scripts/test_task_env.py` 复刻 `eval_policy.main()` 的 arg 装配，只跑官方专家脚本：

```
[sim_smoke] setup_demo OK in 40.1s; subtasks=2
[Subtask 1] Place cup on coaster
[Subtask 2] Place fan on pad
[sim_smoke] play_once OK in 4.2s
  Subtask 1 completed: Cup placed on coaster
  Subtask 2 completed: Fan placed on pad
[sim_smoke] plan_success=True strict_check_success=True
[sim_smoke] obs keys=['observation','pointcloud','joint_action','endpose'] head_rgb=(240,320,3) uint8 mean=183.88
```

日志：`logs/sim_smoke.log`。**这说明**：资产、embodiment、SAPIEN 渲染、CuRobo 规划、物理都在本机正常工作。

---

## 3. Gate 2：1 任务 × 1 episode（Motus + oracle_hse）——**PASS**

| 项 | 值 |
| --- | --- |
| 任务 | `living_room_tidy_2tasks`（阶段：Place cup on coaster → Place fan on pad） |
| track / policy | `oracle_hse` / `Motus` |
| checkpoint | `assets/models/Motus_robotwin2`（sha256 见 §2.1） |
| `--clear-cache` | **`false`**（论文设置；episode 记录里 `cache_cleared: false` 可证） |
| `--max-steps-per-episode` | 1500（spec 默认；无 step-limit 配置时回落到 1000，再被 override 成 1500） |
| 真实 seed | **4,300,000**（`st_seed = 100000 * (1 + --base-seed 42)`，官方 runner 的 seed 规则） |
| 墙钟 | 单 episode `avg_episode_time = 141.8 s`，其中 setup 37.5 s、推理 103.7 s |
| GPU | 单卡 0，峰值约 **38.8 GB / 46.8 GB**，util 约 48% |
| 原始目录 | `results/gate2_20261107_010606_robocombine_oracle_hse_motus/official/` |
| 整理后结果 | `results/gate2_20261107_010606_robocombine_oracle_hse_motus/`（`summary.json` / `per_task.csv` / `episodes.csv`） |

**结果（官方判据，未做任何放宽）**

| 指标 | 值 |
| --- | --- |
| Ordered success | **1 / 1**（`overall_success_rate = 1.0`） |
| 阶段 1 完成 | ✅ step **51** |
| **切换事件** | ✅ step **64**，`source="gt"`、`from_subtask_idx=0 → 1`、`cache_cleared=false`、新指令 `"Place fan on pad"` |
| 阶段 2 完成 | ✅ |
| 总步数 | **173**（上限 1500，未触顶） |
| 失败分类 | timeout 0 / gripper_not_open 0 / subtask_incomplete 0 |

原始证据：`.../tasks/living_room_tidy_2tasks/evaluation_statistics.json`、`task.log`、`command.sh`。

> 这条结果的意义：**官方 Motus checkpoint 在本机、用官方判据、真的完成了两阶段组合任务**，
> 并且 oracle HSE 的交接事件被完整记录。它不是 stub，也不是"规划到就算成功"。

---

## 4. Gate 3：2 任务 × 5 episodes（Motus + oracle_hse）

### 4.1 `living_room_tidy_2tasks`（5 episodes）——**5/5 成功**

| seed | 成功 | 总步数 | 阶段1完成 | 阶段2完成 | cue step | switch step | cue→switch |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 4300000 | ✅ | 173 | ✅ | ✅ | 51 | 64 | 13 |
| 4300001 | ✅ | 253 | ✅ | ✅ | 51 | 64 | 13 |
| 4300002 | ✅ | 465 | ✅ | ✅ | 51 | 64 | 13 |
| 4300003 | ✅ | 174 | ✅ | ✅ | 47 | 48 | 1 |
| 4300004 | ✅ | 159 | ✅ | ✅ | 50 | 64 | 14 |

- `overall_success_rate = 5/5 = 1.0`，`avg_episode_time ≈ 141 s`
- **`cue_step < switch_step` 在 5/5 episode 上都成立**，差值 1–14 步，全部不等长 ——
  这正是 `--clear-cache false`（保留当前 action chunk，跑完再切）的预期行为。
  如果 `clear_cache=true`，切换应当发生在 cue 的同一本步（差值 ≈0）。
- 原始目录：`results/gate3_living_20261107_012314_*/`（`official/` 下有 `task.log` 与
  `evaluation_statistics.json`）。

### 4.2 `office_desk_2tasks`（5 episodes）——**4/5 成功**

| seed | 成功 | 总步数 | 阶段1完成 | 阶段2完成 | cue step | switch step | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 4300000 | ✅ | 172 | ✅ | ✅ | 43 | 48 | |
| 4300001 | ✅ | 285 | ✅ | ✅ | 79 | 80 | |
| 4300002 | ✅ | 423 | ✅ | ✅ | 44 | 48 | |
| 4300003 | ❌ | **1500（触顶）** | ✅ (step 177) | ❌ | 177 | 192 | 第二阶段 1308 步未完成 → `timeout` |
| 4300004 | ✅ | 206 | ✅ | ✅ | 49 | 64 | |

- `overall_success_rate = 4/5 = 0.8`；失败类型：`timeout`（不是夹爪、不是漏阶段）
- 这个失败很有价值：**阶段 1 成功、切换也发生了，是下游技能没在预算内完成** ——
  正是 `docs/02 §4` 里"Downstream Skill Success"要度量的东西，而不是"根本没有切换"。

### 4.3 Gate 3 汇总（两个任务，官方判据）

| 指标 | living_room_tidy_2tasks | office_desk_2tasks | 合计 |
| --- | --- | --- | --- |
| Ordered success | **5/5 = 1.00** | **4/5 = 0.80** | **9/10 = 0.90** |
| Stage-1 success | 5/5 = 1.00 | 5/5 = 1.00 | **10/10 = 1.00** |
| Transition conversion | 5/5 = 1.00 | 5/5 = 1.00 | **10/10 = 1.00** |
| Downstream skill success | 5/5 = 1.00 | 4/5 = 0.80 | **9/10 = 0.90** |
| 平均 episode 时间 | ≈141 s | ≈164 s | — |
| cue→switch 差值 | 13, 13, 13, 1, 14 | 5, 1, 4, 15, 15 | 1–15 步 |

**结论**：在本机配置下（Motus 官方 checkpoint + oracle HSE + `--clear-cache false`），
两个两阶段任务的原子第一阶段 **10/10 全部成功**，**10/10 都发生了指令切换**，
下游 9/10 成功。这满足 `docs/02 §8` 的停止规则，也满足进入 B4–B7 的前置条件（原子成功率足够高）。

原始目录：`results/gate3a_20261107_012314_*`、`results/gate3b_20261107_013845_*`
（各含 `official/`、`summary.json`、`per_task.csv`、`episodes.csv`）。

### 4.4 Gate 3 的可复现命令

```bash
cd /scratch/lijh/SkillHandoffBench
EPISODES=5 TASK=living_room_tidy_2tasks OUT_ROOT=$PWD/results/_official_g3a \
  bash scripts/run_smoke.sh gate2 > logs/gate3_living.log 2>&1     # 复用 gate2 入口，5 episodes
EPISODES=5 TASK=office_desk_2tasks OUT_ROOT=$PWD/results/_official_g3b \
  bash scripts/run_smoke.sh gate2 > logs/gate3_office.log 2>&1
```

> 说明：Gate 3 的"2 任务 × 5 episode"超过了 prompt §5 给**单次 smoke** 的 30 分钟上限，
> 因此拆成两个独立运行、各自 45 分钟上限。单次 smoke 的上限仍然适用于 Gate 2（1 episode）。

---

## 5. 失败与未验证项

见 `docs/04`。这里只列**本轮真实踩到并修掉**的问题，全部在 `docs/01 §9` 有根因分析：

1. torch 安装索引冲突（pybind11 找不到）→ 改用 PyPI + `--only-binary=:all:`
2. 未 pin 的 pillow/h5py/av 走源码编译失败 → 全部 pin 到有 cp310 轮子的版本
3. `omegaconf` 依赖的 `antlr4` 只有 sdist → 单独允许
4. `diffusers` 0.41 需要 torch≥2.10 → pin 0.31.0
5. SAPIEN 缺 `libX11.so.6` → RPM 解包注入
6. SAPIEN 缺 `libvulkan.so.1` → 复用 conda 缓存的 loader
7. `opencv-python` 依赖 X11 且与 headless 共享 `cv2/` 目录 → 用 headless + force-reinstall
8. `open3d` 需 glibc ≥2.27，本机 2.17 → 官方代码里该 import 未被使用，打 **patch 001** 改为可选
9. CuRobo 是硬依赖，且 main 分支 API 不兼容 → 用 v0.7.6 + 自建 nvcc + 增量重试构建
10. `warp-lang` 新版需 glibc 2.27+ → 降到 **1.0.2**（只需 2.14）
11. Motus `deploy_policy` 用 `os.fdopen` 重建 stdout，导致原 wrapper 被 GC 后 fd 1 关闭，后续 print 抛 OSError → **patch 002** 保留强引用
12. `pytorch3d` 缺失时 `camera.py` 的裸 `except:` 里 print 会再次抛错 → **patch 003** 包 try/except

**patch 全部记录在 `docs/patches/`，diff 可审计，且都不触碰成功判据与切换逻辑。**

---

## 6. 复现清单

```bash
cd /scratch/lijh/SkillHandoffBench
bash scripts/preflight.sh --server
bash scripts/fetch_assets.sh assets          # 14.9 GB
python scripts/fetch_models.py --jobs 5     # Motus + Qwen3-VL
bash scripts/fetch_wan.sh                   # Wan2.2 子集
bash scripts/setup_motus_env.sh             # v1（会失败，留作记录）
bash scripts/setup_motus_env_v2.sh          # v2 实际使用
bash scripts/fix_env.sh                     # 收尾（numpy/diffusers/omegaconf/opencv）
bash scripts/setup_x11.sh                   # X11 运行库（RPM 解包）
bash scripts/setup_nvcc.sh                  # micromamba + nvcc 12.1
bash scripts/build_curobo076.sh             # curobo v0.7.6（首轮）
bash scripts/build_curobo_retry.sh          # 增量重试直到全部 .so 就绪
bash scripts/run_smoke.sh gate1
bash scripts/run_smoke.sh gate2
EPISODES=5 bash scripts/run_smoke.sh gate3
```
