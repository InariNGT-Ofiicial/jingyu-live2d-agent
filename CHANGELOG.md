# 更新记录

## 1.4.0-beta.3 — 2026-10-31

本次更新合入 [#1](https://github.com/InariNGT-Ofiicial/jingyu-live2d-agent/pull/1) 和
[#3](https://github.com/InariNGT-Ofiicial/jingyu-live2d-agent/pull/3)。

### 修复

- `bridge_cli.py vts-perform 15` 不再导入缺失的研究脚本，改为将公开表演 15 提交到桥接服务的 VTS 执行链，
  复用任务互斥、取消恢复和最终回执。
- `execute --wait` 在任务被中断时返回失败退出码；连接失败、等待超时和任务记录丢失有明确提示。
- 新增 11 项 CLI 回归测试，覆盖任务等待、错误、中断、输出文件、参数迁移和原 VTS 直连端口兼容。

### 贡献与验证

- 新增贡献指南、PR / Issue 模板、公开文件检查与发布回归清单。
- 提供无需模型、Cubism Core、凭据或 GPU 的合成契约测试；Pillow 测试依赖缺失时直接失败。
- GitHub Actions 检查 Windows Python 3.10 / 3.12 / 3.14 和 Ubuntu Python 3.12，使用 Node.js 24；
  action 固定完整提交 SHA，工作流仅有读取权限。
- 本轮自动验证为 64 项 Python 测试和两组 Node 测试，并检查公开文件、Python / JS 语法。

### CLI 兼容说明

```powershell
python bridge_cli.py vts-perform 15 --url http://127.0.0.1:61942 --output receipt.json
```

需要先启动并配置好桥接服务。该命令始终等待自身任务终态，`--wait` 可以保留；
completed 退出 0，error / interrupted 退出 1。旧 `--port` 会提示改用 `--url`。
`--output` 保存最终任务回执，省略时不再默认写旧研究日志。
`vts-status` / `vts-stream` 仍使用直连 `--port`，默认 8001。

升级时保留 `.local/`、`runtime-config.json` 和导出文件。已有服务由操作者自行安排切换；
本次发布没有重启或替换正在运行的演示服务。

### 验证范围与待办

这是一次 CLI 与维护流程的 beta 更新。本轮未重新执行真实模型、VTS / Spout GPU、视觉、
实际编码或真实 OpenAI / DSH 服务验收；合成测试通过不能替代这些验证。
beta.2 的实录与硬件结果属于历史参考。

[#2 的锯齿修复](https://github.com/InariNGT-Ofiicial/jingyu-live2d-agent/pull/2) 仍在审查，
本版本保留 256 的裁剪蒙版默认值。待哈希 / LF 行尾、跨平台生成一致性及本项目视觉 / 性能验证通过后再合入。

发行物只含公开源码，不含角色模型、贴图、PSD、Cubism Core、个人状态、凭据或生成媒体。
第三方依赖说明见 `THIRD-PARTY.txt` 和 `licenses/`，完整人工验收步骤见 `docs/RELEASE-CHECKLIST.md`。
