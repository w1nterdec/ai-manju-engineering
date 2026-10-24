# 0002：能力与执行侧契约

背景：旧 providers.py 已被外部或测试导入，直接改构造函数会破坏兼容。

备选：替换旧协议；增加新版本侧接口。选择后者：旧 Capabilities/GenerationRequest/Result 保留；adapters.py 定义 CapabilitySpec、注册表、WorkRequest 与离线契约套件，配置 production_version 1.0。

身份资产以独立配置保存角色 ID、参考图集、平台身份 ID 与训练/批准状态；不写入旧 episode 契约。按能力层和镜头路由，并按配置保留回退顺序。注册表只注册受信任代码，不从配置任意 import。

影响：mock 只输出明确 mock=true 的 JSON 占位说明。全部八层和聚合入口可离线验证，但不代表实际生成、训练或转写。新增层、分辨率和时长限制由适配器声明，真实厂商实现暂缺。

回滚：移除新的侧接口和配置，旧命令继续工作。不确定度：中；复核触发：首个真实适配器或供应商新增必需控制项。
