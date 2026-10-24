# 官方资料与验证范围

检索日期：2026-10-24。以下用于确认能力路线存在，不是采购排名，也不是本项目已接通或已达到的效果。接口、模型、音色、地区与授权条款可能变化，实际接入时重新核对。

- [Microsoft Learn：SSML 发音控制](https://learn.microsoft.com/zh-cn/azure/ai-services/speech-service/speech-synthesis-markup-pronunciation)：音素、替代读法和自定义词典；需核对语言、音色和接口支持。
- [阿里云：实时语音合成](https://help.aliyun.cn/zh/model-studio/realtime-tts-user-guide)：介绍使用 `hot_fix` 纠音；具体参数适用范围由相应 API 文档确定。
- [阿里云：CosyVoice HTTP API](https://help.aliyun.cn/zh/model-studio/cosyvoice-tts-http-api)：包含发音纠正参数说明；本项目未实现相应请求转换或真实合成测试。
- [Runway：Gen-4 Image References 指南](https://help.runwayml.com/hc/en-us/articles/40042718905875-Creating-with-Gen-4-Image-References)：展示通过参考图维持角色等视觉元素的工作流；参考控制不能被理解为每个生成镜头必定正确。
- [Black Forest Labs：FLUX.1 Kontext 介绍](https://bfl.ai/blog/flux-1-kontext)：介绍上下文图像编辑和角色保持能力；只作为参考图与编辑路线的依据。
- [ComfyUI：服务器路由官方文档源码](https://github.com/Comfy-Org/docs/blob/main/development/comfyui-server/comms_routes.mdx)：提供队列、历史等接口说明；固定工作流和节点版本属于接入实施工作。

仓库中的镜头拆分、版本冻结、状态链和分阶段验收是工程方案。尚无对照实验能证明该方案较其他方案提升了多少，不将它们写成已有行业结论。
