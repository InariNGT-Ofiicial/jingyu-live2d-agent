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

## 2026-11-05 工具整合

参考 DSH-L2D `1ab1f84`，社区调试台加入以下入口，仍使用独立模型预览，不操作主舞台或改写模型文件：

- 参数探针：从 Cubism 实际读取上下限与默认值，检查写入、网格变化、参数与网格恢复。推荐范围可留空；填写后可选择只提示超出或限制在推荐范围内。取消也恢复现场。结果仅是关闭物理后的单参数测试，不等同完整动作或情绪语义验收。
- 模型参数快照：下载当前参数 JSON，加载旧快照比较新增、删除及范围/默认值变化。
- GIF 节奏分析：本地文件选择后直接在浏览器分析，保留逐帧延时、起止/峰值时间与关键帧候选，并下载 JSON。变帧间隔不会给出误导性的毫秒周期；像素变化不能直接推导动作含义。

原有 `dsh` 导入保持原行为。新增 `source: "dsh-adapter"`：payload 传 `{frame:{controls:{"head.yaw":0.5}},mapping:[{controlId:"head.yaw",paramId:"AngleX",expected:{min:-30,max:30,default:0}}]}`。每个控制项必须有唯一映射，每个模型参数只能被一个控制项绑定，expected 必须与当前参数一致。归一化 0 对应模型 default，正负半轴分别映射到真实上下限。最终仍经过鲸语 pose 编译规则，不支持的通道整组报错，不跳过后冒充完整执行。调试台提供可编辑示例。

CLI：`node tools/analyze_motion_gif.mjs <file.gif>` 输出含 SHA256 的分析 JSON。API 继续使用 `/api/community/import`，新来源与旧来源共用校验/保存流程。核心检查 `node test_model_tools.mjs`；原有录制检查 `python -m unittest test_community_recording`。

来源及改编说明见 `web/community-vendor/DSH-INTEGRATION.md`。未迁入上游 SQLite、Agent 行为循环或待确认语义标签；工作台现有预设存储和主舞台播放引擎继续使用。

本机验收：边界/中性值/重复与缺失映射/旧范围/静止 GIF/disposal/透明/变帧延时检查通过；原有录制两项测试通过。真实 Cubism 中 ParamEyeLOpen 从 1 到 0 的顶点变化约 0.031856，参数及网格恢复误差均为 0；AngleX 的推荐限幅 15→5 通过，隔离物理时仅作 numeric-only 结果。取消恢复、新旧 DSH HTTP 导入均通过。旧 VTS 透明导出 GIF 实测 434 帧、28940ms，保留 60/70ms 变帧间隔。记录位于 `.local/checks/dsh-tools/`。
