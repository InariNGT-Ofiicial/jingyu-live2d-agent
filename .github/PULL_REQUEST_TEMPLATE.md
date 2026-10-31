## 问题与结果

说明具体触发条件、修改后的行为和关联 Issue（如有）。

## 验证

- [ ] `python tools/check_public_tree.py`
- [ ] `python tools/run_checks.py`
- [ ] 涉及硬件、画面或真实服务时，按 `docs/RELEASE-CHECKLIST.md` 附受影响路径的结果

填写运行环境、实际结果和未执行项目及原因；请区分合成测试与真实模型 / GPU 验证。

## 提交检查

- [ ] 未加入模型、贴图、PSD、Cubism Core、原始模型配置、密钥、个人预设、日志或生成媒体
- [ ] 未修改作者原模型；配置 / 预设兼容性和取消恢复已考虑
- [ ] HTTP / CLI / 依赖 / 用户行为变化的文档和示例已同步（如适用）
