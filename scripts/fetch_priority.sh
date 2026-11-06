#!/usr/bin/env bash
# SkillHandoffBench: 关键路径优先的下载队列（替代无差别并行）。
#
# 为什么重写：hf-mirror **不支持 Range 续传**（实测 `curl -r 0-1023` 返回 200 全量），
# 所以"部分下载"没有价值，只能整文件重来。于是按关键路径排序、限制并发数，
# 让最大的必需文件吃到带宽：
#   1) Motus_robotwin2 16.0 GB（checkpoint，blocking 一切）
#   2) Wan2.2 T5 11.4 GB + VAE 2.8 GB（Motus 文本编码器 / VAE，blocking 推理）
#   3) Qwen3-VL-2B 4.3 GB
# 明确**不下载**：Motus_Wan2_2_5B_pretrain（10 GB）、Wan 的 DiT 分片（20 GB）——见 docs/01 §4.1。
set -uo pipefail
ROOT="${SHB_ROOT:-/scratch/lijh/SkillHandoffBench}"
M="$ROOT/assets/models"
HF="${HF_ENDPOINT:-https://hf-mirror.com}"
LOGD="$ROOT/logs"
mkdir -p "$M" "$LOGD"
say() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

get() {  # <url> <dest>
  local url="$1" dest="$2"
  mkdir -p "$(dirname "$dest")"
  say "START $(basename "$dest")"
  curl -L --fail --retry 4 --retry-delay 5 --connect-timeout 30 -s -o "$dest" "$url" \
    && say "OK    $(basename "$dest") $(du -h "$dest" | cut -f1)" \
    || say "FAIL  $url"
}

queue_ckpt() {
  get "$HF/motus-robotics/Motus_robotwin2/resolve/main/mp_rank_00_model_states.pt" \
      "$M/Motus_robotwin2/mp_rank_00_model_states.pt"
  get "$HF/motus-robotics/Motus_robotwin2/resolve/main/config.json" "$M/Motus_robotwin2/config.json"
}

queue_wan() {
  get "$HF/Wan-AI/Wan2.2-TI2V-5B/resolve/main/models_t5_umt5-xxl-enc-bf16.pth" \
      "$M/Wan2.2-TI2V-5B/models_t5_umt5-xxl-enc-bf16.pth"
  get "$HF/Wan-AI/Wan2.2-TI2V-5B/resolve/main/Wan2.2_VAE.pth" "$M/Wan2.2-TI2V-5B/Wan2.2_VAE.pth"
  for f in special_tokens_map.json spiece.model tokenizer.json tokenizer_config.json; do
    get "$HF/Wan-AI/Wan2.2-TI2V-5B/resolve/main/google/umt5-xxl/$f" "$M/Wan2.2-TI2V-5B/google/umt5-xxl/$f"
  done
  get "$HF/Wan-AI/Wan2.2-TI2V-5B/resolve/main/config.json" "$M/Wan2.2-TI2V-5B/config.json"
}

queue_qwen() {
  get "$HF/Qwen/Qwen3-VL-2B-Instruct/resolve/main/model.safetensors" "$M/Qwen3-VL-2B-Instruct/model.safetensors"
  for f in config.json generation_config.json preprocessor_config.json processor_config.json \
           tokenizer.json tokenizer_config.json vocab.json merges.txt video_preprocessor_config.json; do
    get "$HF/Qwen/Qwen3-VL-2B-Instruct/resolve/main/$f" "$M/Qwen3-VL-2B-Instruct/$f"
  done
}

# 清掉"无价值的部分文件"（Range 不支持，半截文件不能用）
rm -rf "$M/Motus_Wan2_2_5B_prestrain" 2>/dev/null || true
rm -rf "$M/Motus_Wan2_2_5B_pretrain" 2>/dev/null || true
rm -f "$M/Motus_robotwin2/mp_rank_00_model_states.pt" 2>/dev/null || true
rm -f "$M/Qwen3-VL-2B-Instruct/model.safetensors" 2>/dev/null || true
rm -f "$M/Wan2.2-TI2V-5B/models_t5_umt5-xxl-enc-bf16.pth" 2>/dev/null || true
rm -f "$M/Wan2.2-TI2V-5B/Wan2.2_VAE.pth" 2>/dev/null || true

queue_ckpt &
queue_wan &
wait
say "critical path done; starting Qwen3-VL"
queue_qwen
say "ALL DONE"
du -sh "$M"/* | sort -h
