# 17 · PRTI 训练复现可行性清单（Gate H）

本轮**不启动任何训练**，只审计"如果要做，缺什么"。依据：论文 §4.2、Appendix D、Table 2。

---

## 1. 论文给出的条件（逐项核对）

| # | 条件 | 论文值 | 来源 | 我们是否具备 | 判定 |
| --- | --- | --- | --- | --- | --- |
| 1 | 初始化 checkpoint | π0.5 **RoboTwin atomic** checkpoint（"initialized from an atomic skill checkpoint trained on the same task distribution"） | App. D | 只有 Motus；**无 π0.5 RoboTwin atomic ckpt** | ❌ 缺失 |
| 2 | 训练数据来源 | "a mixture of isolated atomic skill trajectories from **two atomic data sources**" | App. D | 两个 source 的**具体身份未公开** | `UNKNOWN` |
| 3 | 数据规模 | ~10K episodes、~2M frames、几百条 atomic prompt | App. D | 无 | ❌ 缺失 |
| 4 | 数据性质 | 全部**单技能**轨迹；无组合轨迹 | App. D | — | — |
| 5 | 混合比例 | canonical : PRTI = **1 : 1** | 任务书/论文 | — | 比例已知，但**两侧数据都没有** |
| 6 | 参数更新 | **全参数**后训练 | App. D | 4×A40 可做 small-scale，但 50K step 不现实 | ⚠️ |
| 7 | 算力 | 4 accelerators | App. D | 单卡 | ⚠️ |
| 8 | 步数 | 50K steps | App. D | — | 已知 |
| 9 | batch | global 256 | App. D | — | 已知 |
| 10 | 优化器 | AdamW | App. D | — | 已知（**lr / wd 未给**） |
| 11 | 调度 | cosine + warmup | App. D | — | 已知（**warmup 步数未给**） |
| 12 | EMA | 有 | App. D | — | 已知（**decay 未给**） |
| 13 | 观测 | 3 RGB 视图（1 external + 2 wrist），224×224 | App. D | RoboTwin 能提供 3 视图，但 π0.5 的预处理管线没有 | ⚠️ |
| 14 | 本体状态 | proprioceptive state | App. D | 仿真可取 | ✅ |
| 15 | 指令 | 自然语言 atomic prompt | App. D | 19×(2) 条 stage 指令可得 | ✅ |
| 16 | **PRTI 初始状态采样方式** | "trajectory-supported, physically feasible initial states from successful atomic demonstrations" | App. D.1 | **具体算法未给**（从示范的哪一帧？如何把物体/机器人放回该帧？是否用仿真状态回放？） | ❌ `UNKNOWN`（**最关键**） |
| 17 | 对照 Random | 非结构化扰动 | App. D.1 | 可自行实现 | ✅ |
| 18 | 对照 Reset | 只把机器人复位、物体/接触保持 | App. D.1 | 可实现（需要碰撞检查） | ⚠️ |

---

## 2. 结论

**PRTI 训练复现 = 不可行（本节标记 `PRTI_TRAINING_BLOCKED`）**，缺两样最关键的：

1. **π0.5 RoboTwin atomic 初始化 checkpoint**（论文没有公开链接，RoboCombine 仓库也只有评测代码）。
2. **PRTI 的初始状态采样算法**——这是整个方法的核心。论文只说"从成功原子示范中采样轨迹支持、物理可行的初始状态"，
   但没有给：用哪一帧、如何恢复物体/接触、是否需要在仿真里重放、失败重采样的判据。
   用"看起来合理"的方式自己实现一套，就不能称为复现。

**加上**：两个 atomic data source 的身份、10K episodes 数据、lr/warmup/EMA decay 都未公开。

---

## 3. 如果将来要做，最小可行路径（仅设计，不实施）

| 阶段 | 需要什么 | 现在缺什么 |
| --- | --- | --- |
| 0 | 拿到 π0.5 RoboTwin atomic ckpt | 无公开来源 |
| 1 | 复现"从示范帧构造初始状态"的机制 | 论文未描述；需向作者确认 |
| 2 | 1:1 混合 canonical + PRTI 数据，50K step、bs 256、4 卡 | 单卡 + 无数据 |
| 3 | 用 `oracle_hse` × 19×20 评测 Table 2 | 依赖本轮 Table 1 基线先跑通 |

**本轮不启动训练（遵守任务书）。**
