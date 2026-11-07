#!/usr/bin/env bash
# Gate D 补充：office_organize_2tasks 第 1 个 episode 完成后，官方专家 demo 在第 2 个 seed 上
# **规划卡死**（22 分钟 100% CPU / 0% GPU），因此用 4 个新 seed 补齐到 5 个 episode。
# 仍然：冻结 Motus、oracle_hse、clear_cache=false、1500 步、被动 trace（含接触）。
set -uo pipefail
SHB_ROOT="${SHB_ROOT:-/scratch/lijh/SkillHandoffBench}"
RC="$SHB_ROOT/third_party/RoboCombine"
PY="$SHB_ROOT/envs/motus/bin/python"
P3="$SHB_ROOT/results/phase3"
D="$P3/gateD/office_organize_2tasks"

export CUDA_VISIBLE_DEVICES="${SHB_GPU:-0}"
export ROBOCOMBINE_ASSETS_DIR="$RC/assets"
export PYTHONPATH="$SHB_ROOT/scripts:$RC:$SHB_ROOT/third_party/curobo076/src"
export MOTUS_SAVE_IMAGES=0
export SHB_TRACE_CONTACTS=1
export LD_LIBRARY_PATH="$SHB_ROOT/envs/xlib/usr/lib64:/scratch/lijh/.conda/pkgs/libvulkan-loader-1.4.341.0-h5279c79_0/lib:/scratch/lijh/.conda/envs/gdino_fix/lib:$SHB_ROOT/envs/cuda_home/lib64"
export VK_ICD_FILENAMES="${VK_ICD_FILENAMES:-/etc/vulkan/icd.d/nvidia_icd.json}"

SEEDS="$P3/seeds/ab_4400005_4400008.txt"
mkdir -p "$D" "$P3/seeds"
printf "%s\n" 4400005 4400006 4400007 4400008 > "$SEEDS"

cd "$RC"
SHB_TRACE_JSONL="$P3/trace/office_organize.jsonl" timeout --signal=TERM 2100 \
  "$PY" script/eval_policy.py \
    --config "$RC/policy/Motus/deploy_policy.yml" --overrides \
    --task_name office_organize_2tasks --task_config robocombine_eval --policy_name Motus \
    --seed 42 --episode_num 4 \
    --ckpt_setting "$SHB_ROOT/assets/models/Motus_robotwin2" --ckpt_setting_label motus_robotwin2_official \
    --save_dir "$D" --log_dir "$D" --hse_variant oracle_hse --clear_cache false \
    --max_steps_per_episode 1500 \
    --wan_path "$SHB_ROOT/assets/models/Wan2.2-TI2V-5B" \
    --vlm_path "$SHB_ROOT/assets/models/Qwen3-VL-2B-Instruct" \
    --priority_seeds_file "$SEEDS"
