# 数据契约参考

libero.json 与 aloha.json 记录两套公开样本的来源、维度、FPS和动作语义边界，用于阅读和接入核对；不是CLI的source/profile/targets配置文件。

实际必需字段契约由数据集info.json严格声明，action_contract可在本地manifest中显式提供并注明依据。未知不能凭维度推断。CLI配置示例见configs/demo.json；界面的检查设置会产生新的规则profile ID。
