# 01 · RoboCombine 可行性审计（Phase 0C）

审计时间：2026-11-06 23:00–24:00 CST。审计对象：`third_party/RoboCombine`（官方公开评估代码）。
**本文件每条结论都标注了证据来源：命令、路径或官方文件行号。没有"读过 README 就下结论"的判定。**

审计机：`222.29.51.96`（`lijh`），CentOS 7 / 内核 3.10.0-1160 / glibc 2.17 / driver 550.120 /
5×A40 46068 MiB / `/scratch` 可用 230–232 GB。

---

## 1. 结论摘要（10 项逐条判定）

| # | 检查项 | 判定 | 一句话依据 |
| --- | --- | --- | --- |
| 1 | RoboTwin 仿真与任务资产 | **AVAILABLE**（需自建） | RoboCombine **自带 `envs/`（29 个文件，含 19 个任务）**，但**不含 `assets/`**；资产需从 `TianxingChen/RoboTwin2.0` 取 3 个 zip，共 **14.9 GB** |
| 2 | `Motus_robotwin2` checkpoint | **AVAILABLE** | HF `motus-robotics/Motus_robotwin2`，**16.05 GB** 单文件 `mp_rank_00_model_states.pt`，许可证 **apache-2.0** |
| 3 | Motus 的 WAN 与 VLM 资源 | **AVAILABLE（部分冗余）** | 必需：Wan2.2 的 **T5 11.36 GB + VAE 2.82 GB + umt5 tokenizer + config**，Qwen3-VL-2B **4.27 GB**；`Motus_Wan2_2_5B_pretrain`（10.0 GB）与 Wan 的 3 片 DiT（20.0 GB）**不需要** |
| 4 | Python / CUDA / driver / 显存 | **AVAILABLE（有保留）** | py3.10 可建；driver 550.120 / CUDA 12.4 运行时；A40 48 GB ≥ Motus 推理需求 41 GB（官方 README）。**但无 nvcc、gcc 4.8.5**，任何需要现场编译 CUDA 扩展的包都会失败 |
| 5 | `pi05` adapter 与手上 checkpoint 的兼容性 | **INCOMPATIBLE** | adapter 要求 `pi05_aloha_full_base` + 3 路相机（head/left/right）+ 14 维动作 + `checkpoint/assets/<id>`；手上的 `pi05_droid` 是 DROID 单相机/8 维动作体系 |
| 6 | Oracle HSE 能否在没有 XVLA 时运行 | **AVAILABLE** | `handoff_eval/hse.py:187-207`：`ORACLE_HSE` 只用 `env.subtask_completed[]` 这个特权信号，`_build_real_switch_session()` 在非 `ordered_hse` 时直接返回 `None` |
| 7 | Ordered HSE 的 predictor / X-VLA | **MISSING** | `eval_policy.py:534-549` 要求 `--real-predictor-bundle-dir` + `--real-xvla-model-dir`；仓库 `xvla_progress_predictor/` 只有代码骨架，权重不在仓库、也不在本机缓存 |
| 8 | 原子阶段成功信息 / 切换事件 / 状态记录 / 物理成功标志 | **AVAILABLE** | 任务自带 `subtask_completed[]` 与严格 `check_success()`（`envs/living_room_tidy_2tasks.py:55-115`）；runner 记录 `subtask_completion_steps`、`switch_events`、`episode_details`、`timeout_failures` |
| 9 | 不改判据前提下记录交接前后状态 | **PARTIAL** | 切换事件里已有 `switch_step` / `from_subtask_idx` / `cache_cleared` / `cue_step`；但**没有逐步机器人状态快照**，B4–B7 需要的"交接瞬间 qpos/末端位姿"要靠外部 wrapper 采样（见 §6.3） |
| 10 | 许可证 / 访问 / 下载体积 | **AVAILABLE（有网络前提）** | RoboCombine MIT、Motus Apache-2.0、Qwen3-VL Apache-2.0、Wan2.2 Apache-2.0；RoboTwin 资**产许可 UNVERIFIED**；HF 直连被阻断，走 `hf-mirror.com` |

---

## 2. 代码获取与固定

```bash
git clone --depth 50 https://github.com/AutoLab-SAI-SJTU/RoboCombine.git
```

| 项 | 值 |
| --- | --- |
| 路径 | `/scratch/lijh/SkillHandoffBench/third_party/RoboCombine`（本地同名目录 `third_party/RoboCombine`） |
| commit | **`df237b22bd5c39d705b103daf2b9a8a168c9d453`** |
| commit 时间 | 2026-10-15 10:44:16 +0800 |
| commit 标题 | `docs: ad…`（`git --no-pager log -1 --format=%H|%ad|%s`） |
| 体积 | 3.5 MB（含 `.git`） |
| Python 代码量 | 168 个 `.py`，1,735,463 B |
| LICENSE | **MIT**（`LICENSE` 首行 `MIT License`） |

**官方源码未做任何修改。** 所有适配都在仓库外的新目录里完成（见 §6）。

> 注意：服务器 `git` 是 **1.8.3.1**（CentOS 7 自带），不支持 `git -C`，也不支持 `--format` 与其他选项混用的某些写法；后续脚本一律先 `cd` 再执行。

---

## 3. 必读文件清单（§4.2 要求）

| 文件 | 状态 | 关键内容 |
| --- | --- | --- |
| `README.md` | 已读 | 3 tracks（`full_inst`/`oracle_hse`/`ordered_hse`）、2 policies（`Motus`/`pi05`）、19 任务、`sr_ordered` 主指标；`--clear-cache` 语义（§"Language switching and action chunks"） |
| `docs/runtime_envs.md` | 已读 | Motus 与 pi05 **必须分环境**；`RoboCombine` 只消费解释器路径；checkpoint/资产一律外部注入 |
| `policy/Motus/README.md` | 已读 | 必需外部路径 4 个；ordered 追加 2 个 |
| `policy/pi05/README.md` | 已读 | 需要 `pi05_aloha_full_base`；`checkpoint/assets/<asset_id>` 结构；需要 `curobo` |
| `handoff_eval/specs/robocombine.json` | 已读 | 19 任务、`default_episodes=5`、`default_max_steps_per_episode=1500`、每任务的 `instruction.segments/long` |
| `handoff_eval/runner/run_split.py` | 已读 | 逐任务子进程、seed 逻辑、`--clear-cache` 透传、输出结构 |
| `tests/test_language_switch_runtime.py` | 已读 | 用 fake backend 验证两种 `clear_cache` 与 oracle/predicted 切换，**不需要 GPU/checkpoint** |

---

## 4. 体积预算（先审计再下载）

### 4.1 实测体积（HF API `?blobs=true`）

| 资产 | 来源 | 体积 | 需要？ |
| --- | --- | --- | --- |
| `objects.zip` | `datasets/TianxingChen/RoboTwin2.0` | 3.74 GB | ✅ |
| `background_texture.zip` | 同上 | 10.97 GB | ✅ |
| `embodiments.zip` | 同上 | 0.22 GB | ✅ |
| `Motus_robotwin2/mp_rank_00_model_states.pt` | `motus-robotics/Motus_robotwin2` | 16.05 GB | ✅ |
| `Qwen3-VL-2B-Instruct/model.safetensors` + tokenizer | `Qwen/Qwen3-VL-2B-Instruct` | 4.27 GB | ✅ |
| `Wan2.2-TI2V-5B/models_t5_umt5-xxl-enc-bf16.pth` | `Wan-AI/Wan2.2-TI2V-5B` | 11.36 GB | ✅（T5 文本编码器，`deploy_policy.py:39` 显式加载） |
| `Wan2.2-TI2V-5B/Wan2.2_VAE.pth` | 同上 | 2.82 GB | ✅（`deploy_policy.py:95`） |
| `Wan2.2-TI2V-5B/google/umt5-xxl/*` | 同上 | 0.02 GB | ✅（tokenizer） |
| `Wan2.2-TI2V-5B/diffusion_pytorch_model-0000{1,2,3}` | 同上 | 20.0 GB | ❌ **不需要**：`deploy_policy.py:99` 传 `load_pretrained_backbones=False`，DiT 权重来自 Motus checkpoint |
| `Motus_Wan2_2_5B_pretrain/model.safetensors` | `motus-robotics/Motus_Wan2_2_5B_pretrain` | 10.0 GB | ❌ 同上；本清单最初把它列入，审计后判定冗余（已下载部分保留但不进入运行路径） |
| Motus 源码 | `github.com/thu-ml/Motus` | 3.6 MB（3.6 MB tar） | ✅ |
| 独立 venv（torch 2.4.1+cu124 等） | PyPI / pytorch index | ≈ 8–10 GB | ✅ |

**必需总量 ≈ 53 GB**（资产 14.9 + 权重 34.5 + venv ~8，含 zip 原件峰值另需 ~15 GB）。

### 4.2 磁盘判定

| 时刻 | `/scratch` 可用 |
| --- | --- |
| 2026-11-06 22:54（开工） | 232 GB |
| 下载中 | 230 GB |

→ **不构成阻断**（`docs/04` 记录实际落盘数字）。禁止删除 Simulate 的 checkpoint 与数据（红线 1）。

---

## 5. 环境事实与硬约束

| 事实 | 实测命令 | 影响 |
| --- | --- | --- |
| 无 CUDA toolkit（`nvcc` 不存在，无 `/usr/local/cuda*`） | `which nvcc` → not found；`ls -d /usr/local/cuda*` → 空 | **不能**现场编译 CUDA 扩展（flash-attn / deepspeed / curobo） |
| `gcc 4.8.5`、`glibc 2.17` | `gcc --version`、`ldd --version` | 只接受 manylinux2014 及更早的 wheel；manylinux_2_28 的包会直接失败 |
| **无 Vulkan ICD / loader** | `ls /usr/share/vulkan/icd.d/` → 空；`ldconfig -p \| grep vulkan` → 空 | SAPIEN 渲染可能直接失败 → Gate 1 必须先用最小样例验证（见 §7） |
| 无 `ffmpeg` | `which ffmpeg` → 空 | `--save-video` 不可用（不影响指标，仅无视频） |
| GPU 空闲 | `nvidia-smi --query-gpu=memory.used` → 1–4 MiB/卡 | 单卡 0 号可用；不并行多卡 |
| HF 直连被墙、`hf-mirror.com` 可达 | `curl https://huggingface.co/api/models` 超时；`https://hf-mirror.com` 200 | 下载必须走镜像；31 GB 级文件不支持 Range 续传（实测 `-r 0-1023` 超时），**下载中断须整文件重来** |
| `git` 1.8.3.1 | `git --version` | 见 §2 注意 |

**这些事实直接决定 §6 的适配方式，也决定 `docs/04` 里"哪些能 PASS、哪些只能 PARTIAL"。**

---

## 6. 适配方案（不改动官方源码）

### 6.1 Motus 代码：**仓库自带，无需注入**（一次更正的结论）

`policy/Motus/deploy_policy.py:19-26` 会 import `models.motus`、`wan.modules.t5`、`utils.image_utils`，
并读 `utils/robotwin.yml`、`utils/stat.json`、`expr1/task_instructions.json`。
这些**全部已经在 RoboCombine 仓库里**：

```
policy/Motus/
├── __init__.py                 (29 B, `from .deploy_policy import *`)
├── deploy_policy.py            (17,134 B)
├── deploy_policy.yml           (132 B)
├── expr1/task_instructions.json(2,938 B)   # 19 个任务的 s1/s2/long 指令
├── models/{motus,wan_model,action_expert,und_expert}.py
├── bak/wan/**                  # Wan2.2 的 T5/VAE/attention/scheduler 实现
├── bak/qwen2_5_vl/**           # 备用 VLM 实现
└── utils/{robotwin.yml,stat.json,checkpointer,common,fm_solvers,image_utils,scheduler,vlm_utils}.py
```

> 审计方法更正：第一次用 `Get-ChildItem -File` 只列了文件，漏掉了 `models/`、`bak/`、`utils/`、`expr1/`
> 四个子目录，一度误判为"MISSING"。用 `Get-ChildItem -Recurse` 复核后更正为上表。
> **教训写在这里，因为它直接影响结论：RoboCombine 不需要从 Motus 上游仓库拷贝任何代码。**

**关键差异（不可互换）**：RoboCombine 的 `models/motus.py` 为 33,663 B，上游 `thu-ml/Motus`
的同名文件为 65,899 B——前者是**裁剪后的推理版**，接口（`MotusConfig` 字段、`inference_step` 签名）
按 adapter 需要定制。把上游代码拷进来会破坏接口，因此 `third_party/Motus-src` 只作**参考阅读**，
不进入运行时（`sys.path` 不包含它）。

`utils/stat.json` 已含 `robotwin2` 段的 min/max 归一化统计（14 维），
`utils/robotwin.yml` 给出 `action_dim=14 / state_dim=14 / 384×320 / 8 帧 / 10 步去噪`。

### 6.2 运行环境隔离

| 用途 | 路径 | 说明 |
| --- | --- | --- |
| Motus + 仿真单一进程环境 | `envs/motus/`（新建） | py3.10.21（uv 下载）；torch 2.4.1+cu124；sapien 3.0.0b1 / mplib 0.2.1 与 pyproject pin 一致；transformers 取 Motus 侧要求（Qwen3-VL 需要新版本） |
| ❌ 不动 | `simulate_vla/venv`、`exp40/openpi/.venv` | 红线 5：不在旧环境 `pip install` |

`flash_attn` / `deepspeed` **暂不安装**：本机无 nvcc、gcc 4.8.5，源码编译必失败；且 Motus 推理路径
（`deploy_policy.py` → `models/motus.py`）不 import 它们。若运行期证明必需，按 `docs/04` 的 BLOCKED 记录处理。

**Vulkan**：系统只有 NVIDIA 的 ICD（`/etc/vulkan/icd.d/nvidia_icd.json`，api_version 1.3.277），
**缺 `libvulkan.so.1`**。复用本机 conda 缓存里的 `libvulkan-loader 1.4.341`
（`/scratch/lijh/.conda/pkgs/libvulkan-loader-1.4.341.0-h5279c79_0/lib`）通过 `LD_LIBRARY_PATH` 注入，
不安装系统包、不需要 root。`scripts/run_smoke.sh` 已内置该设置。

### 6.3 交接状态记录（B4–B7 的前置）

官方 `evaluation_statistics.json` 的 `episode_details[]` 已含：`seed`、`success`、`total_steps`、
`subtask_completion_steps`、`subtask_completed`、`switch_events[]`（含 `switch_step`、`cache_cleared`、
`cue_step`）、`predictor_switch_steps`、`timeout_failures`。

**缺口**：没有逐步 `qpos`/末端位姿快照。本轮不实现，方案写进 `docs/02`：
在 `eval()` wrapper 里以只读方式旁路采样（`task_env.robot.get_joint_positions()`），
不触碰 `check_success()` 与切换判据。

---

## 7. Gate 1 已验证的项（原 UNVERIFIED → 已有实测）

| 项 | 结果 | 证据 |
| --- | --- | --- |
| SAPIEN 能否渲染（无 Vulkan ICD 的系统） | **能**：`RENDER OK (48,64,3) float32 mean=0.73`；真实任务相机 `head_rgb=(240,320,3)` | `logs/gate1.log`、`logs/sim_smoke.log` |
| `envs/` 全部 import（sapien 3.0.0b1 + mplib 0.2.1 在 glibc 2.17） | **能**，需 patch 001（open3d 可选导入） | `docs/patches/001_open3d_optional.patch` |
| `tests/test_language_switch_runtime.py` 无需 GPU 即全绿 | **38 passed in 2.43s** | `logs/gate1.log` |
| Motus checkpoint sha256 | `70bc1741b45db5e3eae86510ad3bb1bd1aef04f10b17d8c1ff4dbe099300eb65`（16,046,580,367 B） | `docs/03 §2.1` |
| RoboTwin-OD / background_texture 许可证 | 仍 **UNVERIFIED**（HF 数据集页未声明）→ 只在本机内部使用，不重分发 | — |

---

## 9. 环境适配实录（Gate 1 期间补充，全部是**实测**失败与修复）

这些不是"计划"，是实际踩到的坑；每一条都留了日志与脚本，供下一位复现。

| # | 现象 | 根因 | 处理 | 证据 |
| --- | --- | --- | --- | --- |
| 1 | `pip install torch==2.4.1 --index-url download.pytorch.org/whl/cu124` 整个事务回滚，torch 一个都没装上 | pip 为 torchvision 的构建依赖（pillow→pybind11）也去 pytorch 索引找，那里没有 | 改用 PyPI 的 torch 2.4.1（**cu121**）+ `--only-binary=:all:` | `logs/setup_v2.log:8` |
| 2 | 未 pin 的 pillow/h5py/av 走 sdist 源码编译失败（gcc 4.8.5，无 libjpeg/libswresample 头） | 新版本没有 cp310 wheel | 全部 pin 到有 cp310 manylinux2014 轮子的版本 | `logs/setup_motus_env.log` |
| 3 | `omegaconf==2.3.0` 装不上 | 它要 `antlr4-python3-runtime==4.9.*`，而 4.9.3 只有 sdist | 单独允许该 sdist（纯 Python，无需编译器） | `logs/fix_env.log` |
| 4 | `diffusers` import 报 `torch has no attribute accelerator` | diffusers 0.41 需要 torch≥2.10 的 API | pin `diffusers==0.31.0` | 同上 |
| 5 | `import sapien` → `libX11.so.6: cannot open shared object file` | 本机是纯 headless CentOS 7，`/usr/lib64` 里**没有任何 libX\*** | 用 RPM 解包到 `envs/xlib/usr/lib64`（libX11/Xext/Xrender/xcb/Xau/Xdmcp/Xfixes/Xrandr/Xcursor/Xinerama/Xi/SM/ICE），`LD_LIBRARY_PATH` 注入 | `scripts/setup_x11.sh` |
| 6 | `import sapien` → `libvulkan.so.1` 缺失 | 有 NVIDIA ICD（`/etc/vulkan/icd.d/nvidia_icd.json`，api 1.3.277）但没有 loader | 复用本机 conda 缓存里的 `libvulkan-loader 1.4.341`，`LD_LIBRARY_PATH` + `VK_ICD_FILENAMES` | 实测 `RENDER OK (48,64,3) mean=0.73` |
| 7 | `import cv2` 缺 `libX11` / 卸载 opencv 后 `cv2` 目录被删 | opencv-python 依赖 X11；两个发行包共享 `cv2/` 目录 | 用 `opencv-python-headless` 并 `--force-reinstall --no-deps` | `logs/gate1.log` |
| 8 | `from .planner import CuroboPlanner` 失败 → 所有 task env 无法 import | **curobo 是硬依赖**；`planner.py` 在 curobo 缺失时不定义该符号，而 `robot.py:13` 无条件 import | 构建 curobo v0.7.6（见 #9） | `logs/build_curobo076.log` |
| 9 | curobo main（v0.9）不兼容 | planner.py 用的是 v0.7 旧 API（`curobo.types.math.Pose`、`curobo.wrap.reacher.motion_gen.MotionGen`） | 取 **v0.7.6** tag（`src/` 布局，旧 API） | `third_party/curobo076` |
| 10 | curobo 编译时 `nvcc` 不存在 / `cuda_runtime_api.h` 找不到 | pip 的 `nvidia-cuda-nvcc-cu12` **只有 ptxas，没有 nvcc**；conda 的 CUDA 头在 `targets/x86_64-linux/include` | microMamba 建 `envs/cuda121`（nvcc 12.1.105）+ 组装 `envs/cuda_home` 符号布局（bin/include/lib64/nvvm） | `logs/setup_nvcc.log`、`logs/micromamba_cuda.log` |
| 11 | ninja 并行编译时随机有 `.cu` 的 `.o` 不产出（无 nvcc 报错），`g++` 链接时报 `.o` 不存在 | 未完全定位（单文件 `ninja -v -j1` 可成功）；表现为并行 `--threads=8` 下偶发 | **增量重试**：`scripts/build_curobo_retry.sh` 反复 `setup.py build_ext`，每轮 ninja 只补缺失目标 | `logs/curobo_retry_outer.log` |
| 12 | 资产里只有 `curobo_left_tmp.yml` / `curobo_right_tmp.yml`，而代码读 `curobo_left.yml` / `curobo_right.yml`（内含 `${ASSETS_PATH}` 占位） | RoboTwin 上游用 `update_embodiment_config_path.py` 生成，RoboCombine 未附带 | 用 `sed` 把 `${ASSETS_PATH}` 替换为仓库根，生成两个 yml（**只改资产，不改源码**） | `assets/embodiments/aloha-agilex/curobo_left.yml` |

**结论**：官方 `docs/runtime_envs.md` 假设"你已有一个能跑 RoboTwin 的 Motus 环境"，
但在**纯 headless、无 CUDA toolkit、glibc 2.17** 的机器上，这个假设要付 12 项额外工作才成立。
这些工作全部在用户空间完成，**没有 root、没有覆盖旧环境、没有改官方源码**。

---

## 8. 复现命令（本轮真实执行）

```bash
# 代码
cd /scratch/lijh/SkillHandoffBench/third_party
git clone --depth 50 https://github.com/AutoLab-SAI-SJTU/RoboCombine.git
git clone --depth 1  https://github.com/thu-ml/Motus.git Motus-src

# 体积审计（不下载）
curl -s "https://hf-mirror.com/api/models/motus-robotics/Motus_robotwin2?blobs=true"

# 资产（14.9 GB）
bash scripts/fetch_assets.sh assets
# 权重（Motus/Qwen3-VL，30.3 GB，5 线程）
python scripts/fetch_models.py --jobs 5
# Wan2.2 子集（14.2 GB）
bash scripts/fetch_wan.sh

# 环境（独立 venv，不碰旧环境）
bash scripts/setup_motus_env.sh
```
