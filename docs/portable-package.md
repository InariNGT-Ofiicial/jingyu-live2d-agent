# 本地整合包

Windows x64 本地整合包用于把当前已工作的环境迁移到一个新目录。源码仓库不含模型、生成媒体、声线、权重或编译后的运行时。

双击 `Start-Local.cmd`（`Start-Beta.cmd` 也会转交它），打开 `http://127.0.0.1:61945/`。建议解压到 `D:\Jingyu-1.5`；可含空格，但 CosyVoice 的 FST 原生库需要英文路径。首次加载语音权重会等待一段时间，CUDA 仍需系统显卡驱动，CPU 可运行但较慢。

| 组件 | 本地整合包 |
| --- | --- |
| 当前源码、角色模型、PSD、Cubism Core、贴图、场景、触摸音频 | 随包 |
| Python 3.12、Spout、Pillow、WebSocket、pywin32、GLFW、MCP | `--bundle-runtimes` |
| Node/npm、FFmpeg/ffprobe | `--bundle-runtimes` |
| Electron 网页桌宠 | `--bundle-electron` |
| Python 3.10、CosyVoice2-0.5B、DS A3 参考声线、离线 FST | `--bundle-voice` |
| Minecraft 验证服务端、JRE、Node 模块 | `--bundle-minecraft`，首次创建新世界 |
| VTS、OBS、DSH | 独立安装、自己的 API 授权或账户 |
| Blender、IndexTTS | 研究/制作工具，非工作台默认运行依赖 |

## 构建

准备运行正常的本地环境。`runtime-config.json` 指明 `python`、`capture_python`、`node`、`ffmpeg`、`ffprobe` 的真实路径；其中采集环境使用 Python 3.12 并安装 `requirements-pet.txt`、`requirements-tracking-mcp.txt`。
声线配置 `.local/studio-voice.json` 的 `preset` 指向已验证的预设。模型父目录应包含 `DeepSeek/大肥鱼.model3.json` 和原始作者说明。

```powershell
python tools/package_local.py --model-parent "模型父目录" --stage "D:/build/Jingyu-1.5" --output "D:/build/Jingyu-1.5.zip" --runtime-config runtime-config.json --voice-config .local/studio-voice.json --bundle-runtimes --bundle-electron --bundle-voice --bundle-minecraft --stage-only
# 在 stage 中实际启动，检查网页、桌宠、导出、语音后再封包。
python tools/package_local.py --stage "D:/build/Jingyu-1.5" --output "D:/build/Jingyu-1.5.zip" --archive-stage
```

新建输出目录，不覆盖旧版。脚本把 venv 的基础解释器和依赖合为独立环境，使用相对运行时/声线路径；只复制指定的本地配置，不复制个人预设、API Key、OBS 密码、VTS/DSH 凭据、旧录制或游戏存档。压缩前生成逐文件 SHA-256 清单，压缩后验证 CRC 并生成整个 ZIP 的 SHA-256。

## 升级

保留旧目录，解压新包后先运行。个人预设需要时从旧 `.local/presets.json` 复制到新目录同名位置。API 服务使用自己的配置，VTS 在新目录首次连接需要授权。模型与声线的原始使用说明随本地包保留；此整合包不作为 GitHub 公共附件上传。
