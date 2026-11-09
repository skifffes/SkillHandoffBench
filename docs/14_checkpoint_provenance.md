# 14 · 官方 Checkpoint 与运行环境核验（Gate B）

核验时间：2026-11-09。**不重新下载任何已有资源。**

---

## 1. 结论

| 项 | 状态 |
| --- | --- |
| 权重文件存在、可加载、能产生 checkpoint-backed 推理 | ✅ |
| 文件级完整性（大小 + sha256） | ✅ 有记录 |
| **是否与论文 Table 1 所用的是同一份权重** | ❌ **`CHECKPOINT_PARITY_UNVERIFIED`** |
| 原因 | 论文未给 HF 仓库名/revision；我们的下载记录里也没有保存 HF `revision`/commit |

---

## 2. Motus 主 checkpoint

| 字段 | 值 |
| --- | --- |
| 来源仓库（我们的记录） | HuggingFace `motus-robotics/Motus_robotwin2` |
| revision / commit | **UNKNOWN**（下载时未落盘 HF revision；目录内无 `.cache/huggingface` 元数据） |
| 目录 | `/scratch/lijh/SkillHandoffBench/assets/models/Motus_robotwin2` |
| 文件 | `mp_rank_00_model_states.pt` = **16,046,580,367 B**；`config.json` = 778 B |
| sha256（权重） | `70bc1741b45db5e3eae86510ad3bb1bd1aef04f10b17d8c1ff4dbe099300eb65` |
| 依据 | Phase 0B 的下载日志 `logs/fetch_models.log` + `docs/01_benchmark_feasibility.md` |

`config.json` 关键字段（用于确认是 RoboTwin 版而非通用版）：
`action_dim=14, state_dim=14, num_video_frames=8, video_height=384, video_width=320`。

---

## 3. 伴随资产

| 资产 | 路径 | 大小 | 说明 |
| --- | --- | --- | --- |
| Wan2.2-TI2V-5B | `assets/models/Wan2.2-TI2V-5B` | 14 GB | `Wan2.2_VAE.pth` 2.7 GB、`models_t5_umt5-xxl-enc-bf16.pth` 11 GB、`google/` 21 MB |
| Qwen3-VL-2B-Instruct | `assets/models/Qwen3-VL-2B-Instruct` | 4.0 GB | `model.safetensors` 4,255,140,312 B |
| RoboTwin 仿真资产 | `third_party/RoboCombine/assets` | objects + embodiments + background_texture | 与 RoboTwin 2.0 公开资产一致 |

配套资产同样**没有** revision 记录 → 若论文用的是 Wan2.2 的另一 revision，视觉编码会不同。

---

## 4. 代码版本

| 组件 | 版本 / commit |
| --- | --- |
| RoboCombine | `df237b22bd5c39d705b103daf2b9a8a168c9d453`（2026-10-15，"docs: add paper authors below README title (#7)"） |
| 本地 patch | `docs/patches/001_open3d_optional.patch`、`002_stdout_keepalive_and_pytorch3d.patch`、`004_eval_trace_hooks.patch`（**均不改变动作/判据**；004 在 `SHB_TRACE_JSONL` 未设置时立即 return） |
| Motus 策略适配 | `policy/Motus/`（官方仓库自带） |
| 任务 env | `envs/*_2tasks.py`（19 个）+ 为 Phase 3 审计新增的 `place_phone_stand.py`、`stamp_seal.py`（来自 RoboTwin 上游，**不参与本轮复现**） |

---

## 5. 运行环境

| 项 | 值 |
| --- | --- |
| Python | 3.10.21（`envs/motus`） |
| PyTorch | 2.4.1+cu121 |
| CUDA | 12.1（torch 内建） |
| SAPIEN | 3.0.0b1 |
| mplib | 0.2.1 |
| CuRobo | 0.7.6（源码在 `third_party/curobo076/src`） |
| numpy | 1.26.4 |
| GPU | NVIDIA A40，46,068 MiB（集群有 5 张；本轮只用 1 张，`CUDA_VISIBLE_DEVICES=0`） |
| 驱动 | 550.120 |
| 依赖 workaround | X11 RPM 解包到 `envs/xlib`；conda 版 `libvulkan-loader 1.4.341`；micromamba nvcc 12.1 + conda gcc 11（CuRobo 编译）；`warp-lang==1.0.2` |

这些 workaround 只影响**能否跑起来**，不影响评测语义。

---

## 6. 能证明什么、不能证明什么

**能证明**：
- 评测跑的是真实 checkpoint（不是随机初始化）——Phase 0B 起就有 `checkpoint-backed` 的日志与图像证据；
- 权重文件在多次运行间未被改动（sha256 固定，Phase 1/2/3 结果可逐位复现同 seed 轨迹）。

**不能证明**：
- 这份权重就是论文 Table 1 的那一份；论文没有公开可核对的 identifier。
- 伴随的 Wan2.2 / Qwen3-VL 与论文一致。

→ 按任务书要求记为 **`CHECKPOINT_PARITY_UNVERIFIED`**，且**没有**因为成绩不理想而更换 checkpoint。
