# docs 索引

| 文件 | 状态 | 内容 |
| --- | --- | --- |
| `00_simulate_4_7_audit.md` | ✅ 已完成（2026-11-06） | 旧项目 Simulate 4.7 的真实进度（含证据路径与数字） |
| `01_benchmark_feasibility.md` | ✅ 已完成（2026-11-07） | RoboCombine 10 项逐条判定 + 体积预算 + **12 项环境坑的根因与修复** |
| `02_baseline_protocol.md` | ✅ 已完成（2026-11-07） | B0–B7 定义、任务选择（正式比较前固定）、指标（含分子/分母）、统计分层 |
| `03_execution_report.md` | ✅ 已完成（2026-11-07） | 真实执行记录：Gate 1/2/3 的命令、seed、耗时、日志路径、失败归因 |
| `04_go_no_go.md` | ✅ 已完成（2026-11-07） | `GO / PIVOT / BLOCKED` + 证据 + 预先写死的 PIVOT 触发条件 + 下一轮任务 |
| `patches/` | ✅ | 对官方 RoboCombine 源码的**最小可审计 patch**（2 个，均不触碰判据） |

## 关键结论速查

- **Gate 2**：Motus + oracle_hse，`living_room_tidy_2tasks`，seed 4300000，**1/1 成功**，173 步，
  cue 51 → switch 64（`cache_cleared=false`）。
- **Gate 3**：`living_room_tidy_2tasks` **5/5**、`office_desk_2tasks` **4/5**；
  阶段 1 合计 **10/10**、切换 **10/10**、下游 **9/10**。
- **决策**：`GO`（有条件）。PIVOT 触发条件全部未触发。

执行说明与环境信息见仓库根目录 `prompt.md`；结果包见 `results/`。
