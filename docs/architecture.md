# 架构与数据契约

Python 模块化单体：Streamlit 和 CLI → ingest/contracts → quality → Store review events → metrics/SQL → planning → immutable exports → delivery reconciliation。

## 核心责任

| 模块 | 责任 |
|---|---|
| contracts / ingest | v3 契约、路径边界、checksum、任务与完整轨迹读取 |
| quality | 独立证据、规则配置、必需检查是否完整 |
| metrics / SQL | 一个 episode 一个验收状态，再聚合任务 |
| planning | 三种策略、分为单位的预算、整数解和状态 |
| Store | 追加复核、版本快照、计划与到货记录 |
| delivery | 同源同契约、原批次排除、历史去重、剩余交付量 |
| media / viewer | 相机与原区间来源校验、严格解码、抽查信号、浏览器帧游标 |
| cumulative | 不可变派生分析快照、来源类型与平台契约一致、视频保留、复核安全继承 |
| scenarios / research | 可移植情景、反事实与尝试成本假设；匿名研究记录描述统计 |

源文件保持只读，所有处理结果和人工决定分开保存。snapshot hash 包含实际数据、元数据及任务映射；run hash 再包含规则配置。acceptance hash 再绑定当前复核版本。目标、成本、产能和权重另有版本，方案同时冻结所有引用。

DuckDB 为单机单进程设计。回流的读取历史、查重、计算与写入使用进程内重入锁与事务；单纯 snapshot 事务不足以防止重叠批次的写偏差。不同进程不能共享可写数据库。公开演示每会话内存数据库，避免修改相互影响。

Schema v2 使用幂等建表，增加情景表与版本标记。规则配置新增视频字段会产生新运行ID，旧历史和方案保持只读；升级后应在当前契约下重新生成方案。尚无破坏式迁移。

SQL 的唯一源文件为 `src/robodataops/sql/coverage.sql`，随 Python 包分发，避免安装 wheel 后依赖仓库外部相对路径。
视频联动模板 web/video-viewer.html 同样随wheel分发。视频解码依赖系统FFmpeg，缺失时明确显示未完成。视频时长与轨迹对齐只作metadata一致性检查，不认证物理时钟同步。

累计身份包含表格行、任务、metadata（排除派生文件重定位）与每相机原路径、区间及视频SHA。已获取原片或证据片段均保留；同路径不同内容必须先解决冲突。人工结论仅在规则和证据完全相同、无父结论冲突且目标快照尚无人工结论时迁移。

展示单一内容来源为 portfolio/content.json。build_portfolio.py 读取实际验证报告生成双语HTML与两个README；--check检测分叉。Pages只承载静态介绍、真实录屏与预计算教学情景。Python工作台通过本地、容器或Codespaces运行。

整数规划最小化 Σ w_i(d_i−x_i)/d_i，允许剩余缺口；不设硬性“预算必须花完”。目前未实现二级最小成本目标，等优分配可以不同。每个返回分配都在求解器之外重新检查整数、预算与产能。

当前比例“本方案弥补当前缺口”只在相同初始快照内比较；跨周期使用固定目标达成率。回流 `outstanding` 仅表示原方案交付差额，不冒充全部目标的最新缺口。
