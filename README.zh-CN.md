<!-- Generated from portfolio/content.json. Run script/build_portfolio.py. -->

# RoboDataOps

**从轨迹证据，到下一轮采集决策。**

RoboDataOps 是面向具身数据负责人、采集团队与算法工程师的数据质检与补采决策工作台：把完整 episode 的证据、人工验收口径、任务缺口和有限预算连接起来。

[English](https://github.com/laizhiyin/RoboDataOps/blob/main/README.md) · [中文](https://github.com/laizhiyin/RoboDataOps/blob/main/README.zh-CN.md) · [HTML 1.1.0](https://laizhiyin.github.io/RoboDataOps/?lang=zh) · [GitHub Actions](https://github.com/laizhiyin/RoboDataOps/actions) · [Codespaces](https://codespaces.new/laizhiyin/RoboDataOps?quickstart=1)

## [▶ 点击播放产品讲解视频（约90秒）](https://laizhiyin.github.io/RoboDataOps/?lang=zh#demo)

[![▶ 点击图片播放中文版产品讲解](https://laizhiyin.github.io/RoboDataOps/assets/video-preview-zh.png)](https://laizhiyin.github.io/RoboDataOps/?lang=zh#demo)

**[▶ 点击这里观看中文版](https://laizhiyin.github.io/RoboDataOps/?lang=zh#demo)** · [直接打开 MP4 视频](https://laizhiyin.github.io/RoboDataOps/assets/robodataops-demo-zh.mp4)

点击上方带播放按钮的图片打开视频播放器，再按 ▶ 播放。

30 秒看定位 · 2 分钟看决策 · 5–10 分钟核查实现

[**92** 通过的软件测试](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/reports/test-summary.json) | [**87.49%** 核心包行覆盖率](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/reports/test-summary.json) | [**100 / 100** 独立枚举目标一致](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/reports/validation.json) | [**105** 公开基线 / 兼容轨迹](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/reports/v1-evidence.json)

[验证数字来源](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/reports/test-summary.json)

## 数据交付之后，真正要回答什么？

用户收到多任务示教数据后，需要回答：哪些轨迹按当前用途可计入？哪里仍有缺口？下一轮预算该投向哪里？文件数、异常数和实际可用 episode 数经常不是同一个数字。

产品提供可追溯的验收判断与补采清单，帮助减少重复核对、重复计功和没有依据的采购。工时节省、返工减少与策略收益是待验证的价值假设，尚无真人对照或企业试点结论。

- **数据负责人**：看任务覆盖、未决风险、预算方案与到货差额，明确验收口径。

- **采集 / 质检人员**：定位 episode、字段和帧区间，记录复核理由，按版本导出下一轮任务。

- **算法工程师**：检查平台、维度、FPS 与动作语义边界，追踪训练前数据筛选依据。

## 让每一次计入，都能回到证据。

主演示使用 100 条明确标记的合成故障轨迹：发现 NaN 等技术问题后，查看原始帧证据；对 EP 64 的低运动信号填写依据并驳回，重新计算当前覆盖。合法等待可能有价值，低运动本身不会直接删除数据。

在同一口径下比较等额预算、收益成本比贪心和整数优化，保存包含来源、规则、人工结论、目标与约束的不可变方案。到货验收排除原批次和已登记轨迹；累计页再生成有父版本血缘的新快照，回算全部任务缺口。

- **01 读取与检查**：LeRobot v3 薄适配，按 metadata 找到完整轨迹，严格核对声明与实际 dtype、维度、索引和时间。

- **02 证据与复核**：单项 / 批量确认、驳回、暂缓与恢复；追加历史。视频片段联动动作 / 状态游标。

- **03 规划与解释**：情景保存 / 导入 / 导出、三种策略比较、预算与产能反事实、显式尝试成本下的成品率敏感性。

- **04 回流与累计**：同源同契约验收、重复计功防护、累计分析快照、内容不变时继承复核；冲突拒绝静默合并。

## 理解数据，先明确它不能证明什么。

共享 Parquet / MP4 分片不等于 episode。视频根据原 metadata 的相机和时间偏移定位；5 段 LIBERO 仿真片段保留来源路径、区间、转换与 SHA256。解码、黑帧和冻结检查有明确抽查范围；未下载、无法解码和未发现异常分别显示。metadata 游标联动不构成物理同步认证。

第二来源 ALOHA 验证 14 通道、50 FPS，与 LIBERO 的 7 维动作、10 FPS 区分。动作单位、绝对 / 增量控制和坐标系缺证据时保持 unknown；维度相同也不能推断语义一致。

按当前技术与复核口径计入，不表示任务成功、信息量充足或模型训练收益。默认目标、成本、权重和产能均为模拟情景，实际输入必须记录依据。累计产物是保留原始 ID 的分析快照，不是重编号的训练数据集。

- **技术阻断优先**：阻断 → 必需检查未完成 → 未决复核 → 计入。每条 episode 归入一个状态，多项发现不会重复扣数。 [状态归约实现](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/src/robodataops/metrics.py)

- **来源独立标记**：合成缺陷用于测试，公开仿真样本用于兼容验证，模拟成本用于决策演示；三类证据不互相替代。 [设计取舍](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/docs/decisions.md)

## 从产品判断，追到实现和反例。

技术栈：Python + PyArrow 读取列式数据，DuckDB / SQL 汇总验收状态，SciPy / HiGHS 求解整数分配，Streamlit 提供本地工作台，FFmpeg 提供视频解码与片段提取。静态双语案例页通过 GitHub Pages 发布；它提供预计算教学交互，完整 Python 工作台通过本地、Docker 或 Codespaces 运行。

补采模型最小化加权剩余缺口比例 L = Σ wᵢ(dᵢ−xᵢ)/dᵢ；整数 xᵢ 满足 0≤xᵢ≤min(dᵢ,capᵢ)，Σcᵢxᵢ≤预算。金额使用整数分；独立检查求解结果的预算、整数与容量约束，区分最优、可行未证最优、超时无解与不可行。该目标衡量数量覆盖，不直接最大化机器人能力。

- **具身数据与 Python**：完整 episode 读取、规则证据、显式动作契约与视频来源校验。 [quality.py](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/src/robodataops/quality.py)

- **SQL 与口径**：先按 episode 归约，再按任务聚合，避免多发现导致数量膨胀。 [coverage.sql](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/src/robodataops/sql/coverage.sql)

- **定量决策**：整数优化、两项基线、反事实与独立枚举 oracle。 [planning.py](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/src/robodataops/planning.py)

- **工程与回归**：固定依赖、文件校验、追加审计、事务写入、并发收货去重、CLI 与远端 CI。 [关键回归反例](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/tests/test_review_regressions.py)

- **产品能力**：用户任务、状态工作流、验收边界、可用性协议和完整版本规划。 [产品需求文档](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/docs/PRD.md)

- **一次真实工程迭代**：收货去重曾存在跨连接竞态：增加进程内串行事务与并发反例。V1 视频时长规则也用不匹配区间回归，避免证据生成中断。这里是工程审查迭代，尚非真人用户反馈。 [问题—修改—复测](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/docs/iteration-log.md)

## 验证的分母，与结果一起展示。

自动化测试覆盖真实软件行为；100 个小型受控情景用独立穷举核对最优目标，并对三项策略执行 300 次约束检查，保留贪心与优化打平的结果。合成质量测试使用固定受控回归并包含合法静止负例，尚无独立冻结测试集；不把注入缺陷命中率描述成真实行业准确率。

公开样本固定 revision：LIBERO 100 条 / 16,048 帧 / 5 任务，ALOHA 5 条兼容样本；另有每任务 4 条的 20 条公开保留池用于模拟回流。公开样本技术检查结果不构成人工质量金标准。5 段视频仅覆盖所列第一相机片段，其余相机与区间未做全量验收。

尚未开展：3–5 位相关用户对照、30–50 条独立人工标注、机器人训练与 rollout、真实采集成本试点。仓库提供空研究模板、描述性统计 CLI 和实验协议；空模板会被拒绝，绝不生成虚构研究成果。

- **软件与优化证据**：环境、依赖、种子、样本、oracle 与未开展项目均有结构化记录。 [验证报告](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/reports/validation.md)

- **浏览器与视频交互**：实际浏览器检查桌面、390px 手机布局、视频定位与累计快照流程。 [浏览器检查记录](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/reports/browser-smoke.json)

- **真人与训练实验**：交叉平衡任务顺序，记录完成时间与关键错误；训练固定任务、预处理、预算和至少 3 个 seed，区分质检与分配消融。 [待执行协议与模板](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/docs/research/README.md)

## 带着数据，一起复现。

环境要求 Python 3.12、uv；视频功能需要系统 FFmpeg。仓库自带已署名的离线分析缓存，默认流程无需下载全部机器人数据。首次安装 Python 依赖需要网络。软件默认英文，侧栏 Language / 语言 可切换中文；CLI 支持 --lang en / --lang zh。切换语言保留数据、规则、复核和预算状态，原始数据及审计 JSON 不改写。

运行工作台后，依次体验问题复核、预算比较、公开视频和累计快照。LIBERO 来源配合 public_delivery 演示累计：100 → 120 条，每任务新增 4 条；保留池是预先留出的公开仿真数据，不能当作实际新采。GitHub Pages 页面提供静态教学案例，不能运行 Streamlit 后端。

- **数据获取与许可**：LIBERO / ALOHA 的固定版本、选择规则、文件 SHA256 和独立数据许可见各缓存目录 NOTICE。重新获取执行 fetch-libero 或 prepare_evidence.py；视频下载约 80MB，并非默认启动步骤。 [LIBERO 来源与片段归属](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/data/public_sample/NOTICE.md)

- **系统与接口**：CLI 和界面共用领域实现。本地持久模式保存 var/workbench.duckdb；演示模式按会话隔离。多进程、权限管理和海量任务调度留待真实团队试点。 [架构与运行边界](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/docs/architecture.md)

```bash
git clone https://github.com/laizhiyin/RoboDataOps.git
cd RoboDataOps
uv sync --frozen
ROBODATAOPS_DEMO_MODE=1 uv run streamlit run app.py

# 检查、规划、独立验证与测试
uv run robodataops audit --source data/public_sample --db :memory:
uv run robodataops plan --source data/demo --budget 800 --db :memory:
uv run python -m robodataops.validation
uv run pytest -q --cov=robodataops --cov-fail-under=80

# 构建与核对同一内容来源的网页 / README
uv run python script/build_portfolio.py
uv run python script/build_portfolio.py --check

# 容器运行（已内置 FFmpeg）
docker compose up --build
```

## 展示可解释的能力，也明确贡献范围。

这是 AI 辅助开发项目。项目新增实现覆盖用户流程、v3 薄适配、验收状态、证据连接、预算模型、累计血缘和验证工具；开源组件负责数据生态、存储、求解和界面基础。调用 HiGHS 不等于自行发明优化算法，使用 AI 生成代码也不等于已证明独立编码能力。

求职者应亲自完成三次可复现演练：增加规则及合法负例；修改 SQL 且证明不重计；增加业务约束并解释求解结果。个人主导、亲自修改与面试可解释范围应按实际经历补充，当前不虚构实习、用户访谈或独立贡献比例。

下一步优先收集真人任务反馈与人工标签，再做小型策略实验。商业扩展按试点需要增加服务端数据库、权限、对象存储、后台作业、供应商与排期，而不以功能数量替代真实采用证据。

- **贡献与开源归属**：RoboDataOps 代码 MIT；公开数据与第三方组件遵循各自许可。 [贡献说明](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/docs/contributions.md)

- **后续验证**：真实用户、实际成本、训练收益与商业试点的完成条件分别记录。 [仍待完成的外部验证](https://github.com/laizhiyin/RoboDataOps/blob/v1.1.0/docs/NEXT_STEPS.md)

## 静态预算教学案例

以下结果由同一 Python 规划模块预计算；成本与权重均为模拟。网页切换预算不会调用实时后端。

| 预算 / 元 | 等额预算 L | 贪心 L | 最优 L |
|---:|---:|---:|---:|
| 200 | 3.550 | 3.500 | 3.450 |
| 350 | 2.800 | 2.900 | 2.800 |
| 500 | 2.150 | 2.200 | 2.150 |
| 800 | 0.950 | 0.950 | 0.900 |
