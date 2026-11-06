#!/usr/bin/env bash
# SkillHandoffBench: 可复现的最小 benchmark 入口（Gate 1 → 2 → 3）。
#
# 约束（来自 prompt.md §5）：
#   - 单卡（默认 GPU 0），不训练，不跑 19 任务全量
#   - 单次 smoke 有 wall-clock 上限（默认 30 分钟，用 `timeout` 硬杀并留日志）
#   - `--clear-cache` 必须显式固定：论文里"保留当前 action chunk"= false
#
# 用法：
#   bash scripts/run_smoke.sh gate1
#   bash scripts/run_smoke.sh gate2                 # 1 任务 × 1 episode（oracle_hse, Motus）
#   bash scripts/run_smoke.sh gate3                 # 2 任务 × 5 episodes
#   TRACK=full_inst TASK=living_room_tidy_2tasks bash scripts/run_smoke.sh gate2
#
# 关键环境变量（都有默认值，见下）：
#   SHB_ROOT / MOTUS_PY / ASSETS / CKPT / WAN / VLM / TRACK / TASK / EPISODES / MAX_MINUTES
set -uo pipefail

SHB_ROOT="${SHB_ROOT:-/scratch/lijh/SkillHandoffBench}"
RC="$SHB_ROOT/third_party/RoboCombine"
MOTUS_PY="${MOTUS_PY:-$SHB_ROOT/envs/motus/bin/python}"
ASSETS="${ROBOCOMBINE_ASSETS_DIR:-$SHB_ROOT/third_party/RoboCombine/assets}"
CKPT="${MOTUS_CKPT:-$SHB_ROOT/assets/models/Motus_robotwin2}"
WAN="${MOTUS_WAN_DIR:-$SHB_ROOT/assets/models/Wan2.2-TI2V-5B}"
VLM="${MOTUS_VLM_DIR:-$SHB_ROOT/assets/models/Qwen3-VL-2B-Instruct}"
TRACK="${TRACK:-oracle_hse}"
TASK="${TASK:-living_room_tidy_2tasks}"
TASK2="${TASK2:-office_desk_2tasks}"
EPISODES="${EPISODES:-1}"
MAX_MINUTES="${MAX_MINUTES:-30}"
OUT_ROOT="${OUT_ROOT:-$SHB_ROOT/results/_official}"
CLEAR_CACHE="${CLEAR_CACHE:-false}"      # 论文设置：保留当前 chunk
GPU="${SHB_GPU:-0}"

say() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }
hr() { say "------------------------------------------------------------"; }

export CUDA_VISIBLE_DEVICES="$GPU"
export ROBOCOMBINE_ASSETS_DIR="$ASSETS"
# curobo（v0.7.6，src 布局）与仓库本身都要在 PYTHONPATH 上
CUROBO_SRC="${CUROBO_SRC:-$SHB_ROOT/third_party/curobo076/src}"
export PYTHONPATH="$RC:$CUROBO_SRC${PYTHONPATH:+:$PYTHONPATH}"
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
# 关闭 Motus 每步保存预测帧网格（会写大量 png，拖慢 rollout）
export MOTUS_SAVE_IMAGES="${MOTUS_SAVE_IMAGES:-0}"

# Vulkan loader：系统只装了 NVIDIA 的 ICD（/etc/vulkan/icd.d/nvidia_icd.json），
# 但没有 libvulkan.so.1。复用本机 conda 缓存里的 libvulkan-loader 1.4.341（不安装、不改系统）。
VK_LIB_DIR="${VK_LIB_DIR:-/scratch/lijh/.conda/pkgs/libvulkan-loader-1.4.341.0-h5279c79_0/lib}"
# X11 运行库：本机是纯 headless，没有 libX11；SAPIEN 直接链它。用 RPM 解包到用户空间。
XLIB_DIR="${XLIB_DIR:-$SHB_ROOT/envs/xlib/usr/lib64}"
CUDA_HOME_LOCAL="${CUDA_HOME_LOCAL:-$SHB_ROOT/envs/cuda_home}"
CONDA_CC_LIB="${CONDA_CC_LIB:-/scratch/lijh/.conda/envs/gdino_fix/lib}"
EXTRA_LIBS=""
[ -d "$XLIB_DIR" ] && EXTRA_LIBS="$XLIB_DIR"
[ -e "$VK_LIB_DIR/libvulkan.so.1" ] && EXTRA_LIBS="${EXTRA_LIBS:+$EXTRA_LIBS:}$VK_LIB_DIR"
[ -d "$CONDA_CC_LIB" ] && EXTRA_LIBS="${EXTRA_LIBS:+$EXTRA_LIBS:}$CONDA_CC_LIB"
[ -d "$CUDA_HOME_LOCAL/lib64" ] && EXTRA_LIBS="${EXTRA_LIBS:+$EXTRA_LIBS:}$CUDA_HOME_LOCAL/lib64"
if [ -n "$EXTRA_LIBS" ]; then
  export LD_LIBRARY_PATH="$EXTRA_LIBS${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  export VK_ICD_FILENAMES="${VK_ICD_FILENAMES:-/etc/vulkan/icd.d/nvidia_icd.json}"
fi

preflight_paths() {
  local bad=0
  for p in "$RC" "$MOTUS_PY" "$ASSETS" "$CKPT" "$WAN" "$VLM"; do
    if [ ! -e "$p" ]; then echo "MISS $p"; bad=1; else echo "OK   $p"; fi
  done
  for f in "$CKPT/mp_rank_00_model_states.pt" "$WAN/models_t5_umt5-xxl-enc-bf16.pth" \
           "$WAN/Wan2.2_VAE.pth" "$VLM/config.json" "$RC/policy/Motus/models/motus.py" \
           "$RC/policy/Motus/utils/robotwin.yml" "$ASSETS/embodiments" "$ASSETS/objects"; do
    if [ -e "$f" ]; then echo "OK   $f"; else echo "MISS $f"; bad=1; fi
  done
  return $bad
}

gate1() {
  hr; say "GATE 1-a: 任务列表（官方 CLI）"
  ( cd "$RC" && "$MOTUS_PY" handoff_eval/runner/run_split.py \
      --spec robocombine --track "$TRACK" --policy Motus \
      --checkpoint "$CKPT" --motus-wan-dir "$WAN" --motus-vlm-dir "$VLM" \
      --list-tasks 2>&1 | tee "$SHB_ROOT/logs/gate1_tasks.txt" | tail -25 )
  say "task count = $(wc -l < "$SHB_ROOT/logs/gate1_tasks.txt")"

  hr; say "GATE 1-b: 官方契约测试（无 GPU / 无 checkpoint）"
  ( cd "$RC" && "$MOTUS_PY" -m pytest tests/test_language_switch_runtime.py -q 2>&1 | tail -20 )

  hr; say "GATE 1-c: 最小依赖 import"
  "$MOTUS_PY" - <<'PYEOF'
import importlib, sys
mods = ["numpy", "torch", "sapien", "mplib", "toppra", "transforms3d", "h5py", "cv2",
        "yaml", "easydict", "omegaconf", "einops", "safetensors", "transformers",
        "tokenizers", "accelerate", "diffusers"]
bad = 0
for m in mods:
    try:
        mod = importlib.import_module(m)
        print(f"OK   {m} {getattr(mod, '__version__', '')}")
    except Exception as exc:
        bad = 1
        print(f"FAIL {m}: {type(exc).__name__}: {exc}")
import torch
print("torch:", torch.__version__, "cuda:", torch.version.cuda, "available:", torch.cuda.is_available(),
      "devices:", torch.cuda.device_count())
sys.path.insert(0, ".")
try:
    import envs  # noqa: F401
    print("OK   envs package")
except Exception as exc:
    bad = 1
    print(f"FAIL envs: {type(exc).__name__}: {exc}")
raise SystemExit(bad)
PYEOF

  hr; say "GATE 1-d: checkpoint / 权重完整性（sha256）"
  for f in "$CKPT/mp_rank_00_model_states.pt"; do
    [ -e "$f" ] && { say "sha256 $f"; sha256sum "$f"; } || say "MISS $f"
  done
  if [ -f "$CKPT/SHA256SUMS" ]; then cat "$CKPT/SHA256SUMS"; fi

  hr; say "GATE 1-e: GPU 可用性"
  nvidia-smi --query-gpu=index,name,memory.total,memory.used,utilization.gpu \
    --format=csv,noheader | sed -n '1,5p'

  hr; say "GATE 1-f: SAPIEN 能否建场景并渲染（Vulkan 关键检查）"
  "$MOTUS_PY" - <<'PYEOF'
import numpy as np
try:
    import sapien.core as sapien
    eng = sapien.Engine()
    scene = eng.create_scene()
    cam = scene.add_camera("c", 64, 48, 1.0, 0.1, 10.0)
    scene.step()
    scene.update_render()
    cam.take_picture()
    rgb = cam.get_picture("Color")[:, :, :3]
    print("RENDER OK", rgb.shape, float(rgb.mean()))
except Exception as exc:
    print("RENDER FAIL", type(exc).__name__, exc)
    raise SystemExit(3)
PYEOF
}

run_split() {  # args...
  local run_tag="$1"; shift
  local out="$OUT_ROOT/$run_tag"
  mkdir -p "$out" "$SHB_ROOT/logs"
  local started; started=$(date +%s)
  say "CMD: $MOTUS_PY handoff_eval/runner/run_split.py $*"
  say "wall-clock cap = ${MAX_MINUTES} min"
  ( cd "$RC" && timeout --signal=TERM "$((MAX_MINUTES * 60))" \
      "$MOTUS_PY" handoff_eval/runner/run_split.py "$@" ) 2>&1 | tee "$SHB_ROOT/logs/${run_tag}.log"
  local code=${PIPESTATUS[0]}
  local elapsed; elapsed=$(( $(date +%s) - started ))
  say "exit=$code elapsed=${elapsed}s (timeout would be 124)"
  return $code
}

gate2() {
  hr; say "GATE 2: 1 任务 × ${EPISODES} episode（$TRACK / Motus / --clear-cache $CLEAR_CACHE）"
  run_split gate2 \
    --spec robocombine --track "$TRACK" --policy Motus \
    --checkpoint "$CKPT" --checkpoint-label motus_robotwin2_official \
    --motus-wan-dir "$WAN" --motus-vlm-dir "$VLM" \
    --episodes "$EPISODES" --task-filter "$TASK" \
    --clear-cache "$CLEAR_CACHE" \
    --output-root "$OUT_ROOT"
  collect "$OUT_ROOT" "gate2"
}

gate3() {
  hr; say "GATE 3: 2 任务 × ${EPISODES} episodes（$TASK / $TASK2）"
  run_split gate3 \
    --spec robocombine --track "$TRACK" --policy Motus \
    --checkpoint "$CKPT" --checkpoint-label motus_robotwin2_official \
    --motus-wan-dir "$WAN" --motus-vlm-dir "$VLM" \
    --episodes "$EPISODES" --task-filter "$TASK" --task-filter "$TASK2" \
    --clear-cache "$CLEAR_CACHE" \
    --output-root "$OUT_ROOT"
  collect "$OUT_ROOT" "gate3"
}

collect() {  # <output-root> <tag>
  local root="$1" tag="$2"
  local latest; latest=$(ls -1dt "$root"/robocombine/*/Motus/* 2>/dev/null | head -1)
  [ -n "$latest" ] || { say "no official run dir found under $root"; return 1; }
  local run_id; run_id=$(basename "$latest")
  local dest="$SHB_ROOT/results/${tag}_${run_id}"
  mkdir -p "$dest"
  cp -r "$latest"/. "$dest"/ 2>/dev/null
  say "copied official run -> $dest"
  [ -f "$dest/summary.json" ] && { say "summary.json:"; head -c 2000 "$dest/summary.json"; echo; }
  for f in "$dest"/tasks/*/evaluation_statistics.json; do
    [ -f "$f" ] && { say "stats: $f"; head -c 1200 "$f"; echo; }
  done
}

main() {
  local mode="${1:-gate1}"
  hr; say "SkillHandoffBench run_smoke mode=$mode"
  say "RC=$RC"; say "PY=$MOTUS_PY"; say "ASSETS=$ASSETS"; say "CKPT=$CKPT"
  say "WAN=$WAN"; say "VLM=$VLM"; say "TRACK=$TRACK TASK=$TASK CLEAR_CACHE=$CLEAR_CACHE GPU=$GPU"
  preflight_paths || { say "PREFLIGHT FAILED（见上面的 MISS）"; }
  case "$mode" in
    gate1) gate1 ;;
    gate2) gate2 ;;
    gate3) gate3 ;;
    preflight) say "preflight only" ;;
    *) echo "usage: $0 {gate1|gate2|gate3|preflight}"; exit 2 ;;
  esac
}

main "$@"
