# 研究与产品有效性验证

状态：工具和协议已实现；尚无真实参与者、独立人工金标准、训练 rollout 或实际采集报价。空模板不代表研究结果。

## 1 软件正确性

运行 `uv run pytest -q --cov=robodataops --cov-fail-under=80` 和 `uv run python -m robodataops.validation`。pytest 验证完整轨迹、字段与时间、复核状态、SQL 去重、整数约束、到货并发、累计血缘、视频与情景边界。规划另以独立穷举核对100个小问题，不只和同一个求解器比对。公开样本兼容报告见 reports/v1-evidence.json，浏览器实测见 reports/browser-smoke.json。

## 2 人工质量标签

从 LIBERO / ALOHA 原始样本中抽30–50条，包含未告警样本、困难边界和合法静止。先按原 episode / session 划开发与冻结集合，再生成变体。至少两位审阅者独立标“问题 / 无问题 / 证据不足”，记录区间、相机、原因与分歧处理。使用 annotation-template.csv；不根据系统告警倒填真值。

真实缺陷很少时报告案例与误报率、置信区间和分母，不能估计没有阳性依据的召回率。黑帧、冻结和短轨迹需结合用途判断，技术损坏与任务失败分别标注。

## 3 真人产品任务

遵循 ../usability-protocol.md，招募3–5名相关人员，用难度相近的任务交叉平衡工作台与现有表格/脚本的顺序。冻结正确答案；记录培训、完成、时间、关键错误、求助、原话。产品设计目标为完成率至少80%，正确性不下降时配对中位用时改善约30%；这些是目标，不是结果。

使用 study-template.csv 记录匿名信息。汇总：

```bash
uv run robodataops evaluate-study --input path/to/real-anonymous-records.csv --output reports/user-study.json
```

工具拒绝空模板、重复条件、非正用时与非法完成值，只做描述性统计，不验证参与者身份或自动推断显著性。请勿将可识别个人信息、未授权录音或企业私有数据提交到公开仓库。

至少记录一次真实观察 → 产品取舍 → 代码修改 → 同任务复测。当前 iteration-log.md 仅有真实工程审查迭代。

## 4 训练收益实验

使用 Linux 仿真，先选2–4个 LIBERO 任务、固定 BC / ACT、相同预处理、任务内选样规则、训练步数和至少3个训练 seed。固定 rollout 初始状态与评测预算，报告每任务和总体成功率及不确定性。

分开消融：原始数据 vs 质检筛选（相同训练量）；等预算随机/均分 vs 贪心 vs 优化（相同任务内选样）。不要同时改变模型、训练时长、任务选择与数据量后归因于质检。预注册停止规则和失败案例。仿真收益不外推真机。

## 5 实际业务收益

一个完整交付周期记录真实报价、尝试数、成品率、复核工时、返工与合格交付。合格单价与尝试成本分开；成品率敏感性只有在尝试成本语义下使用。净收益扣除部署、标注与维护成本，和真实现有流程比较。

## 开源工具与来源

- [LeRobot](https://github.com/huggingface/lerobot)：数据格式、机器人数据生态与后续 BC/ACT 训练工具。本项目使用薄适配避免为了质检安装训练栈。
- [LIBERO](https://github.com/Lifelong-Robot-Learning/LIBERO)：后续仿真基准；当前公共缓存来自固定 Hugging Face 转换版本。
- [ALOHA](https://github.com/tonyzhaozh/aloha)：双臂研究生态；当前兼容样本是公开仿真插入数据，不是真机部署结果。
- [PyArrow](https://github.com/apache/arrow)、[DuckDB](https://github.com/duckdb/duckdb)：列式读取与可解释 SQL 聚合。
- [SciPy](https://github.com/scipy/scipy)、[HiGHS](https://github.com/ERGO-Code/HiGHS)：整数优化。独立穷举 oracle 位于 validation.py。
- [pytest](https://github.com/pytest-dev/pytest)、[Playwright](https://github.com/microsoft/playwright-python)、[FFmpeg](https://github.com/FFmpeg/FFmpeg)：回归、浏览器实测与视频检查。

数据获取：仓库自带100条LIBERO、5条ALOHA与20条保留池。`uv run robodataops fetch-libero`按固定revision/seed恢复公开表格；`uv run python script/prepare_evidence.py`获取指定视频并提取片段。网络下载会缓存到ignored data/raw，数据license独立见各NOTICE。
