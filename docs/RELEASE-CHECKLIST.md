# 发布回归清单

每次发布从候选提交执行，并将下面的记录复制到发布说明或维护记录。
此文件是执行清单，不代表所有项目已经通过。

## 候选与自动检查

- [ ] 记录完整 commit SHA、版本、日期、Windows / 浏览器 / Node / Python / FFmpeg / VTS 版本与 GPU。
- [ ] 确认工作区和待发布 diff；检查没有模型资产、Core、凭据、个人状态、日志或生成媒体。
- [ ] `python tools/check_public_tree.py` 和 `python tools/run_checks.py` 通过。
- [ ] GitHub `public-tree` 和全部 `contracts` 矩阵通过；保留运行链接。
- [ ] 在拥有模型使用授权的本机环境完成下方受影响路径；每项填写通过、失败或未执行及原因。

CI 的合成数据不包含作者动作和物理，不能代替下面的真实回归。
CI 不安装 SpoutGL、不运行 VTS、不连接真实 OpenAI / DSH，也不编码实际视频。

## 独立验证环境

备份个人 `.local/` 和 `runtime-config.json`，保留现有服务。使用独立 checkout、测试配置与空闲端口，
例如 `python launch.py --model-dir "模型目录" --port 61943 --no-browser`。
不要把测试浏览器或 CLI 指向正在演示的 61942 端口；CLI 显式使用 `--url http://127.0.0.1:61943`。
真实模型仅本地读取，禁止上传到 CI 或发布附件。

```powershell
python launch.py --model-dir "模型目录" --check
python -c "from model_profile import write_profile; write_profile()"
python -m unittest test_compiler test_driver_integration test_planner test_beta test_vts_deploy test_presets
.local/vts-capture/Scripts/python.exe -m unittest test_vts_capture
node test_engine.mjs
node test_driver_integration.mjs
```

生成 profile 时，先在该终端把 `L2D_MODEL_DIR` 设为同一个模型目录。
上述单测和真实服务均应在独立验证 checkout 运行。

## 网页、协议与状态

- [ ] 新配置能够启动；缺模型或依赖时能给出可执行的错误提示。
- [ ] 网页左右视线、微笑、手势进入 / 收回、原物理、连续轨迹和表情叠加正常。
- [ ] 暂停、停止、重新播放和后台恢复符合预期，最终回到中立状态。
- [ ] 网页导出仍使用同一个 PIXI WebGL context 内的独立模型和 RenderTexture。
- [ ] 透明 GIF 边缘与时长正常；MP4 按背景色合成，ffprobe 确认 H.264、尺寸、帧率、时长。
- [ ] 保存个人预设、重启后恢复、重播无需模型调用、确认删除；旧配置和旧预设保留。
- [ ] HTTP / CLI 以任务最终 `completed / error / interrupted` 为准；入队成功不算完成。
- [ ] 真实 OpenAI Chat Completions、Responses 和 DSH 分别记结果；仅 fixture 通过时如实标记。
      输出与截图不包含 Key、认证头、DSH 凭据或私人提示词。

## VTS 与原生采集

- [ ] 仅首次授权测试副本；热部署只修改 `Jingyu-Author-Comparison`。
      执行前后核对作者源模型与物理文件哈希，原始文件未变。
- [ ] 运行独立 Python 3.12 的 `vts_capture.py --probe`，核对发送器、GPU、尺寸与 alpha 范围。
      多发送器要求明确选择；VTS 可见、不最小化，启用 Spout2 和透明背景。
- [ ] VTS 与采集 Python 使用同一 GPU；任何图形偏好修改由操作者主动执行，并记录回退方式。
- [ ] 重载后等待出场过渡并预热帧缓冲，再从完整表演开头采样；保留真实构图与作者物理。
- [ ] 同一计划分别导出透明 GIF 和背景合成 MP4；核对首尾、动作方向、进入 / 收回和音视频属性。
- [ ] 检查 `capture-report.json`：采样时间、unique / repeated / late frames、源尺寸和 alpha。
      sender frame counter 缺失时明确标记不可用；像素变化不能证明每个渲染帧都被采集。
- [ ] 导出中取消：恢复完成前保持独占；恢复后可执行下一任务。
- [ ] 断流、整段静止、尺寸改变、错误发送器、非透明 GIF 输入应失败，并恢复 VTS。
      不允许静默替换采集源。

历史参考：1.4.0-beta.2 曾以 960×600、15 FPS、约 29 秒 / 434 帧验证完整 VTS 表演，
没有重复 / 迟到帧；这是既往特定环境结果。新候选提交与新硬件必须重新记录，不能沿用为本次通过。

## 发布与回退

- [ ] 核对 `beta.json`、服务版本、启动检查与 README 的产品版本一致；协议版本号按其兼容规则维护。
- [ ] 更新用户可见行为、依赖、迁移和已知限制。未执行的硬件 / 服务测试单独列出。
- [ ] 只打包 `git archive` 对应的公开源码，不打包整个本地目录或 CI 临时数据。
      创建 tag / Release 前人工核对归档内容与第三方许可清单。
- [ ] 记录上一个可用 tag 或完整 SHA。回退代码时保留个人设置、预设和已导出文件，
      先停止测试副本，再核对受影响的 VTS 专用副本配置是否恢复；不要替换作者原模型。

建议记录格式：

```text
候选 SHA / 版本 / 日期：
环境与 GPU：
CI 运行链接：
真实模型单测：
网页 / GIF / MP4：
VTS / Spout / 取消恢复：
OpenAI Chat / Responses / DSH：
未执行项目及原因：
采样报告摘要（脱敏）：
已知问题与回退 SHA：
验收人：
```
