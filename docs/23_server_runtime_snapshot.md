# 23 · 服务器运行目录快照（开跑前的最后一块证据）

日期：2026-11-10（UTC+8）。目的：把"实际被执行的代码"与"官方 commit"钉死，
补上 `docs/19`/`configs/robocombine_public_protocol_lock.yaml` 里"锁的是代码，不是服务器现场"这一缺口。

---

## 1. 服务器运行目录

| 项 | 值 |
| --- | --- |
| 路径 | `/scratch/lijh/SkillHandoffBench/third_party/RoboCombine` |
| `git rev-parse HEAD` | **`df237b22bd5c39d705b103daf2b9a8a168c9d453`** |
| 官方远端 `git ls-remote origin HEAD` | **`df237b22bd5c39d705b103daf2b9a8a168c9d453`**（同一天实测，官方仍未前进） |
| 工作区 | 3 个文件 modified + 2 个原子任务 env untracked（见 §2、§3） |
| 是否存在 stash / 额外分支 | 无（`git status` 只显示上述项） |

---

## 2. 三个改动文件的**逐文件指纹**（工作区 vs 官方 HEAD）

| 文件 | 工作区 sha256 | `git show HEAD:<file>` sha256 | diff |
| --- | --- | --- | --- |
| `envs/camera/camera.py` | `6493ca49…1f9943` | `e4d17e99…32832dd` | 11+/2− |
| `policy/Motus/deploy_policy.py` | `192f5204…86b9461e` | `1be3bedf…407a27b3` | 4+/0− |
| `script/eval_policy.py` | `72b042f9…39617ca` | `8281fac6…5d22949b7` | 17+/1− |

`git diff --numstat` 合计：**32 行新增 / 3 行删除**。

### 2.1 四个 patch 的完整语义（逐条）

| # | 位置 | 改动 | 影响算法行为？ |
| --- | --- | --- | --- |
| 001 | `envs/camera/camera.py` 顶部 | `import open3d` → `try/except ImportError`（缺库时 `o3d=None`） | **否**，仅导入；`fps()` 在 `pointcloud:false` 下不被调用 |
| 003 | 同文件 `except:` 分支 | `print("missing pytorch3d")` 外包 `try/except OSError` | **否**，仅日志 |
| 002 | `policy/Motus/deploy_policy.py` 顶部 | 保存 `sys.stdout/stderr` 引用，防止 GC 后 `print` 抛 `OSError` | **否**，仅日志管道 |
| 004 | `script/eval_policy.py` 共 8 处 | 插入 `shb_trace.hook(...)` 纯调用；未设 `SHB_TRACE_JSONL` 时 `hook()` 第一行 return | **否**（另有 A/B 实证，见下） |

**patch 004 的非干预证据**：同 seed 三跑（无 trace / 只记 action / 全量）——
`stats` 逐位相同、`task.log` 388 行逐行相同、173 条 action `max_abs_diff=0.0`、
静态扫描无 RNG（`docs/08 §5`，`results/phase2/trace/ab_comparison.json`）。

**未改动**：`_base_task.setup_demo`、seed 生成、专家筛选（`eval_policy.py:775-790`）、
`check_success`、`sequential`/`sr_ordered` 计算、HSE 切换（`handoff_eval/hse.py`）、chunk 长度。
即：**没有任何 patch 触及动作、初始化、切换时序或成功判据**。

---

## 3. 两个 untracked 文件

| 文件 | 来源 | 是否影响 19 任务评测 |
| --- | --- | --- |
| `envs/place_phone_stand.py` | Phase 3 从 RoboTwin 上游复制（B0 基线用） | **否**（不在 `robocombine.json` 的 19 任务里，不会被加载） |
| `envs/stamp_seal.py` | 同上 | **否** |

另有历史遗留 `./-`（159 MB，Phase 3 一次 shell 重定向写错产生的 trace 文本，内容为 JSONL 记录，
**不是**评测产物、不影响任何运行），未删除，仅在此登记。

---

## 4. 正式运行的参数与环境快照

| 项 | 值 |
| --- | --- |
| 入口 | `handoff_eval/runner/run_split.py`（官方） |
| 固定参数 | `--spec robocombine --policy Motus --task-config robocombine_eval --episodes 20 --max-steps-per-episode 1500 --clear-cache false --base-seed 42` |
| checkpoint | `assets/models/Motus_robotwin2`（sha256 `70bc1741…300eb65`，= HF LFS oid） |
| WAN / VLM | `assets/models/Wan2.2-TI2V-5B`、`assets/models/Qwen3-VL-2B-Instruct` |
| Python | `/scratch/lijh/SkillHandoffBench/envs/motus/bin/python`（3.10.21 / torch 2.4.1+cu121 / SAPIEN 3.0.0b1） |
| 关键 env | `ROBOCOMBINE_ASSETS_DIR`、`PYTHONPATH=$ROOT/scripts:$RC:$ROOT/third_party/curobo076/src`、`LD_LIBRARY_PATH=<xlib>:<vulkan-loader>:<conda gcc>:<cuda_home>/lib64`、`VK_ICD_FILENAMES`、`MOTUS_SAVE_IMAGES=0`、`CUDA_VISIBLE_DEVICES=0` |
| trace | **关闭**（未设 `SHB_TRACE_JSONL`）→ patch 004 全程惰性 |
| 外层超时 | 每个 (track, task) invocation `timeout 28800`（8h），远大于实测最长 ~8h/20eps |

---

## 5. 与"23 项协议检查 PASS"的关系（诚实说明）

`scripts/check_protocol_lock.py` 检查的是**仓库文件与运行产物的一致性**（spec hash、scene hash、
README 声明、runner 默认值、专家筛选锚点、`hse.flush_pending_switch`、所有 `command.sh` 的标志位）——
它**不能**证明"服务器上正在执行的那份文件"没有被人临时改过。

本文件补的正是这一块：**服务器 HEAD + 三个文件的 sha256 + 完整 diff** 已落盘（§2），
任何人可以拿 `git show HEAD:<file> | sha256sum` 与上表对照，逐字节确认。

> 建议：全量跑完后，再对同一目录跑一次本节命令，确认 sha256 与今天一致（防止跑动期间被改）。

---

## 6. 演练批次（已按批准启动）

| 项 | 值 |
| --- | --- |
| 任务 | `breakfast_prep_2tasks`（尚无 base 42 的正式 N=20 结果） |
| 轨道 | `oracle_hse`、`full_inst` 各 20 eps = **40 rollouts** |
| 启动方式 | `setsid nohup bash scripts/run_all_paper_table1.sh --tasks breakfast_prep_2tasks --tracks oracle_hse,full_inst` |
| 输出 | `results/paper_table1/full/<track>/breakfast_prep_2tasks/attempt1/` |
| 日志 | `logs/paper_table1/full/supervisor_rehearsal.out` + `logs/paper_table1/full/<track>__breakfast_prep_2tasks__a1.log` |
| 状态查询 | `bash scripts/paper_table1_status.sh` |
