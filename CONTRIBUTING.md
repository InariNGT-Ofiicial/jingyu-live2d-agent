# 参与鲸语开发

欢迎提交小而完整的修复。新功能、参数映射或架构调整，请先说明场景与预期行为，
避免把界面、协议和渲染链路的大改混进同一个 PR。维护者审查后再合并。

## 不需要模型也能运行的检查

Python 3.10+、Node.js 24；以下命令在仓库根目录执行：

```powershell
python -m venv .local/test-env
.local/test-env/Scripts/python.exe -m pip install -r requirements-test.txt
.local/test-env/Scripts/python.exe tools/check_public_tree.py
.local/test-env/Scripts/python.exe tools/run_checks.py
```

Linux 对应解释器为 `.local/test-env/bin/python`。Node 不在 PATH 时，给最后一条命令
添加 `--node "完整的 node 可执行文件路径"`。

`run_checks.py` 在 `.local/checks/` 下建立并清理一次性副本，用手写的合成表情、线性动作、
物理输出归属和 VTS 映射运行全部 Python 单测与两组 Node 测试，并检查 Python / JS 语法。
它只复制公开代码输入，不读取本机模型、Core、个人设置、密钥、预设或已有生成 profile；
不会启动 HTTP 服务、连接 VTS、调用模型服务或更改 GPU 设置。
Pillow 是必须依赖，缺少时直接失败，避免 RGBA 测试被静默跳过。

合成数据验证编译、通道冲突、协议、采样和取消等代码契约；它不验证作者模型的真实动作、
物理或画面。涉及这些行为的 PR 还须按 [发布回归](docs/RELEASE-CHECKLIST.md) 记录人工结果，
未执行的项目写明原因。不要把合成测试通过称为 VTS 实录或视觉验收通过。

## 提交范围与证据

- 在个人分支开发；一个 PR 解决一个明确问题，描述触发条件、修改后的行为和测试结果。
- 修复应补充能重现问题的回归用例。界面、模型或导出变化附脱敏截图或采样统计，并说明硬件与版本。
- HTTP / CLI 字段或错误行为变化，同时更新 `BETA-API.txt`、示例及相关帮助文本。
- 用户配置和个人预设应能保留；不要让测试或升级流程覆盖 `.local/`、`runtime-config.json`。
- 不要为测试连接贡献者或维护者正在运行的服务；真实调试使用独立副本和空闲端口。
- 新增贡献致谢时同步更新 README 的贡献者名单，使用公开用户名和可回查的 PR / 提交链接；
  如实区分已合入、审查中和已撤回的提案，合入或重新提交后更新对应记录。

## 需要保留的实现约束

- 网页导出在同一个 PIXI WebGL context 内使用独立模型和 RenderTexture；
  第二个 WebGL context 会遇到 Cubism singleton shader 问题。
- 作者原模型只读。VTS 热部署只写 `Jingyu-Author-Comparison` 专用副本，保留作者物理与配置，
  并验证停止、取消和异常后能恢复。不要以直接驱动物理输出替代语义输入。
- VTS Spout2 是实时 GPU RGBA 流；重载后等待出场过渡并预热帧缓冲。
  VTS 与采集 Python 必须位于同一 GPU。帧计数不可用时如实标记，不能伪造连续帧证据。
- GIF 是二值透明，普通 H.264 MP4 没有透明通道。采集失败应报错，不悄悄切成网页或屏幕截图。
- VTS 依赖可选。SpoutGL 0.1.1 使用独立 Windows Python 3.12 环境，
  不要因为本机使用较新的主解释器而升级或混装采集环境。

## 公开文件边界

只提交桥接源码、必要示例和依赖说明。禁止提交模型、贴图、PSD、MOC、原始动作 / 表情 / 物理 / VTS 配置、
Cubism Core、令牌、API Key、个人预设、运行记录或生成媒体。保留第三方原版权头、来源与许可。
角色模型从作者渠道取得；本项目不授予角色资产的再分发权利。

`check_public_tree.py` 检查 Git 跟踪文件和未忽略的新文件，拒绝排除路径、非 UTF-8 文件、非法 JSON
和少量高置信度密钥形式；只输出文件名和规则，不回显密钥。它不能发现所有凭据或判定资产授权。
提交前仍需检查 `git diff --cached --stat` 和具体 diff。发现真实密钥时先撤销密钥，
不要在公开 Issue / PR 粘贴原值或完整本机配置。

## 审查和优先级

维护者先核对 PR 的最新 head、diff、CI 和已有讨论，再按风险处理：

| 优先级 | 情况 | 合并前要求 |
| --- | --- | --- |
| P0 | 凭据公开、原模型被写入、个人数据丢失 | 先止损和核对影响范围，阻止发布 |
| P1 | 启动失败、动作/取消无法恢复、错误导出、必需检查失败 | 修复并完成受影响路径回归 |
| P2 | 功能改进、适配、性能和文档 | 明确范围与证据后排队审查 |

CI 通过只是审查输入。不要自动合并外部贡献；人工 review 需核对配置兼容性、资产边界与回归证据。
