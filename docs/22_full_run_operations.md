# 22 · 全量评测的后台运行手册（关机能跑吗？）

结论先说：**可以。你的电脑可以关机，服务器上的评测会继续跑。**
本轮只写了运行器与手册，**没有启动任何 GPU 作业**。

---

## 1. 为什么可以关机

| 依赖 | 在哪 | 关掉本地电脑会怎样 |
| --- | --- | --- |
| 评测进程（`eval_policy.py`） | **服务器** `222.29.51.96` | 不受影响（`setsid` + `nohup` 已脱离终端） |
| SSH 会话 | 本地 ↔ 服务器 | 断开后进程继续（关键：必须 `setsid nohup` 启动，不能前台跑） |
| PKU VPN | 本地 | 断开不影响服务器；**只影响你下次连上去看进度** |
| 我（agent） | 本地 | 关机后我无法监控/重连，作业仍在跑 |
| 仿真/模型/资产 | 服务器本地盘 | 不需要外网 |

**唯一必须"在线"的时刻是启动那一下**：先连 VPN → SSH 到服务器 → `setsid nohup ... &` → 之后就可以关电脑。

---

## 2. 什么会真的打断它

| 事件 | 作业 | 恢复方式 |
| --- | --- | --- |
| 你关机 / 断 VPN | ✅ 继续 | 无 |
| SSH 掉线 | ✅ 继续（已 setsid 脱离） | 无 |
| **服务器重启 / 断电 / 管理员 kill** | ❌ 中断 | 重新启动 supervisor，**会自动跳过已完成的 (track, task)** |
| GPU 被别的进程占满 | ⚠️ 当前 invocation 可能 OOM | supervisor 有 `wait_gpu_free`；单次失败会自动换目录重试（最多 2 次） |
| 单个 invocation 超 8h | ⚠️ 截断（exit=124） | 自动换新目录重试；仍不满 20 就标 `GIVEUP` 并继续下一个 |

---

## 3. 启动 / 查看 / 停止

```bash
# 0) 先连 VPN，SSH 到服务器
ssh lijh@222.29.51.96
cd /scratch/lijh/SkillHandoffBench

# 1) 先看还剩什么（不烧卡）
bash scripts/run_all_paper_table1.sh --dry-run

# 2) 后台启动（关键：setsid + nohup，脱离终端）
mkdir -p logs/paper_table1/full
setsid nohup bash scripts/run_all_paper_table1.sh \
  > logs/paper_table1/full/supervisor.out 2>&1 &
echo $! > logs/paper_table1/full/supervisor.pid
disown || true

# 3) 随时看进度（只读，几秒）
bash scripts/paper_table1_status.sh          # 人看
bash scripts/paper_table1_status.sh --json   # 机读

# 4) 停止
kill "$(cat logs/paper_table1/full/supervisor.pid)"     # 温和：跑完当前 invocation 后退出
pkill -9 -f run_all_paper_table1.sh                     # 立刻停（当前 episode 会丢，需重跑该组合）
```

**安全设计**：脚本用 `flock` 单实例锁，重复启动第二个会直接 `exit=3`，不会两个进程抢同一张卡。

---

## 4. 断点续跑的正确姿势

- 状态目录：`results/paper_table1/full/<track>/<task>/attempt<N>/`
- 判据：**只认 `episode_details` 的条数**（不认 `metadata.total_successes`，那个会累计）
- 重启 supervisor 时：
  - 已满 20 eps 的组合 → `SKIP`（含历史上 `gateE_deep` 里已完成的两个任务）
  - 未满的 → 从 **下一个 attempt 号** 继续（不向旧目录追加，避免 `successful_seeds` 污染样本总体）
- **禁止**手工往已有 `attempt` 目录续跑。

---

## 5. 规模与资源

| 项 | 数值 |
| --- | --- |
| 已完成 | 4 个组合 = 80 eps（living/office × 2 轨道） |
| 剩余 | **34 个组合 = 680 eps** |
| 单组合耗时（实测） | oracle ≈ 4–6 h / 20 eps；full ≈ 6–8 h / 20 eps |
| 单卡总时长 | **≈ 100–110 h（约 4.5 天）** |
| 5 卡并行 | 需改成分片（每卡不同 `STATE` 子目录 + `SHB_GPU=i`），脚本当前**只支持单实例**，约 24–30 h |
| 磁盘 | 每个组合 < 5 MB（`MOTUS_SAVE_IMAGES=0`，不开 trace），680 组合 < 4 GB；`/scratch` 现有 158 GB |
| 产出位置 | `results/paper_table1/full/`（新目录，**不覆盖** `gateE_deep`/`probe`） |

---

## 6. 跑完之后怎么用

```bash
# 逐组合完整性 + 与论文对照
python scripts/check_paper_reproduction.py \
  --root results/paper_table1/full --track oracle_hse --expected-episodes 20 \
  --json results/paper_table1/check_full_oracle.json

# 汇总表（19 任务 × 2 轨道）
bash scripts/paper_table1_status.sh
```

`status` 的 `ordered` 列按 `s1_step ≤ s2_step` 重算，`env` 列是环境终局成功——两个数**永远分开报**。

---

## 7. 没做的事

- 未启动任何评测（GPU 空闲）。
- 未加 crontab 自启（服务器没有用户 crontab；重启后需手动再跑一次 supervisor，脚本会自动续跑）。
- 未做多卡分片（需要再写一层 shard 参数，本轮未做）。
