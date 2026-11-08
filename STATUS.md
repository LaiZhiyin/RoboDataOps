# RoboDataOps V1.0.0 交付状态

软件与招聘展示版本已实现。真人需求验证、机器人策略和实际采集收益仍待实验，不能据软件完成推断这些效果。

## 已完成

- 四页工作台：数据概览、问题复核、补采规划、累计快照。
- LeRobot v3完整episode读取，严格字段/平台/动作契约、互斥验收状态、追加单项/批量复核与恢复。
- 5段真实公开LIBERO仿真视频，原区间与SHA256归属，视频与动作/状态游标联动，严格解码与抽查信号。
- 100条LIBERO / 16,048帧 / 5任务，5条ALOHA / 14通道 / 50FPS，以及20条公开保留池；均可离线分析。
- 预算三策略、独立约束检查、情景保存/导入/导出、预算/产能反事实与尝试成本敏感性。
- 原契约到货核对、并发去重、不可变累计分析快照，视频保留、内容冲突拒绝与安全复核继承。
- 85项自动化测试通过、核心包行覆盖率86.57%；100/100独立枚举一致、300次约束检查。精确证据见reports。
- 实际浏览器：四页流程、情景保存、视频第20帧定位、100→120累计、390px手机；双语网页与10,000帧×14通道渲染通过。
- 约90秒真实操作视频、双语字幕、真实截图、可交互预算教学；HTML/README/README.en共用内容与报告构建。
- Python wheel含SQL与HTML资源；固定依赖、CLI、Docker/Codespaces配置、GitHub CI与Pages工作流。
- 真实Git基线c115d6e；不补造历史，独立代码审查问题已修复并有回归。

## 入口

- 案例页：https://laizhiyin.github.io/RoboDataOps/ 。
- 仓库：https://github.com/laizhiyin/RoboDataOps 。
- 完整工作台：`ROBODATAOPS_DEMO_MODE=1 uv run streamlit run app.py`，或Docker / Codespaces。
- 同源网页/README内容：portfolio/content.json；`uv run python script/build_portfolio.py --check`。
- 软件/优化、公开兼容、浏览器与视频证据：reports/validation.md、v1-evidence.json、test-summary.json、browser-smoke.json、portfolio-browser.json、video.json。
- 远端Linux测试、容器构建启动和Pages部署结果以GitHub Actions实际运行记录为准；本地容器配置未在此Mac上运行Docker。

## 外部验证与运行边界

本地单机单进程，DuckDB持久模式或会话隔离演示。Pages仅托管静态案例、真实视频和预计算教学；尚无独立免登录公网Python后端。累计产物保留原始源ID，用于分析，不是直接训练split。

独立人工金标准、3–5位真实用户对照、至少3seed训练/rollout和实际成本试点仍待执行，协议和空记录模板已提供。AI辅助开发与开源组件归属明确，个人能力需要本人解释、修改与复现。
