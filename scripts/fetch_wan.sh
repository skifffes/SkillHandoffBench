#!/usr/bin/env bash
# SkillHandoffBench: 只取 Motus 运行时真正需要的 Wan2.2-TI2V-5B 子集。
# 为什么不全下：diffusion_pytorch_model-*（20 GB）是 Wan 原生 DiT 权重，Motus 用
# `load_pretrained_backbones=False` 并从 Motus_robotwin2 checkpoint 载入全部权重，
# 因此这三片不需要（见 docs/01 的体积审计）。T5 + VAE + tokenizer + config 必需。
set -uo pipefail
ROOT="${SHB_ROOT:-/scratch/lijh/SkillHandoffBench}"
DEST="$ROOT/assets/models/Wan2.2-TI2V-5B"
BASE="${HF_ENDPOINT:-https://hf-mirror.com}/Wan-AI/Wan2.2-TI2V-5B/resolve/main"
mkdir -p "$DEST/google/umt5-xxl"
say() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

get() {  # relpath
  local rel="$1"
  say "start $rel"
  curl -L --fail --retry 5 --retry-delay 5 --connect-timeout 30 -s -o "$DEST/$rel" "$BASE/$rel" \
    && say "OK   $rel $(du -h "$DEST/$rel" | cut -f1)" || say "FAIL $rel"
}

get "models_t5_umt5-xxl-enc-bf16.pth" &
get "Wan2.2_VAE.pth" &
for f in special_tokens_map.json spiece.model tokenizer.json tokenizer_config.json; do
  get "google/umt5-xxl/$f"
done
get "config.json"
get "configuration.json"
wait
say "wan subset done:"
du -sh "$DEST"; find "$DEST" -type f | sort
