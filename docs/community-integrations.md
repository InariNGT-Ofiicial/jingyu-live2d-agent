# 社区动作调试台

启动鲸语后从首页进入「社区调试台」。独立预览窗口读取模型的真实范围、部件列表和初始状态。在窗口中调整配饰或动作滑杆，点击「开始录制」与「结束录制」，即可下载 timeline-v1 或命名保存为预设。模型部件透明度只用于该窗口预览。录制按约 100 毫秒采样，以实际时间戳为准，最长 58 秒。关闭预览窗口后，已保存的预设可在主舞台播放。

面板和录制交换格式参考《Live2D 配饰面板 · 源码分享》及《Live2D 动作调试台 · 源码分享》。鞋子开关按“穿着”展示，写入时反转脱鞋参数。关键帧中省略的通道使用模型默认值。录制计划末尾预留 0.2 秒回正。

## 供外部宿主使用

向 `POST /api/community/import` 提交 `{source,payload}`。成功返回 `{plan,compiled}`。宿主可将 plan 交给现有的 /api/execute 或 /api/presets/save。导入操作本身只校验，不启动表演。

| source | payload 示例 | 接入范围 |
|---|---|---|
| tuner | {"format":"live2d-tuner/timeline-v1","duration":1,"keyframes":[{"t":0,"v":{"ParamAngleX":-10}},{"t":1,"v":{}}]} | 稀疏时间线、作者手势关节、语义参数和配饰参数。物理输出和未知通道会返回错误。 |
| dsh | {"controls":{"head.roll":0.4,"gaze.x":-0.5}} | 每次将一个 SemanticMotionFrame 转成独立姿态，支持头三轴、视线双轴、躯干倾斜和侧移。 |
| maibot | {"type":"state:emotion","data":{"emotion":"happy"}} | happy/shy/sad、thinking，以及 nod/blink/smile 单次动画消息。 |

DSH-L2D 源自 [3163252](https://github.com/tequed232/DSH-L2D/tree/3163252/packages/core/src) 的 motion-contract.ts 和 motion-intent.ts。MaiBot 消息归一化源自 [2eeda7e](https://github.com/Maboroshinatsu/maibot-deskpet-plugin/tree/2eeda7e/deskpet-app/src/renderer/services/host) 的 maibot-protocol.ts。web/community-vendor 存放移除 TypeScript 类型并改用 .mjs 导入的模块及两份上游许可证。上述协议入口供宿主主动投递，持续订阅上游事件、音频、Electron 悬浮窗不在本次集成范围。
