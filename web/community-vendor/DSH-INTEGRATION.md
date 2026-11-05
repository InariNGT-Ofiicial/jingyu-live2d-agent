# DSH 工具迁移来源

来源：tequed232/DSH-L2D，提交 1ab1f84b183f6ab1d9afa6d32735349f23b091a0（2026-11-05）。MIT 许可证见同目录 DSH-L2D-LICENSE.txt。

`gif-analysis.mjs` 改编自 `tools/motion-gif/analyze.mjs`：去除 SQLite 和文件读写依赖，改为浏览器/Node 共用；逐帧采样；修复静止峰值与 disposal 后差异比较；提供真实时间戳，变帧间隔不推断毫秒周期。输出仅描述像素变化，不能确认肢体或情绪语义。

`omggif.mjs` 来自该提交的 omggif 1.0.10 vendor，唯一改动是 CommonJS 导出转为 ESM。原作者 Dean McNamee 的 MIT 许可证保留在文件头。

`web/model-tools.mjs` 复用双层范围、模型适配与范围变化检测的设计，按鲸语参数结构重新实现，补齐 undefined/NaN/反转范围检查，以模型 default 为中性值。

`web/parameter-probe.mjs` 复用鲸语已有 StressRunner 的隔离手工渲染方式，并吸收 DSH 探针的写入/恢复分离验证。结果明确标记 isolated-core-no-physics，不计作主舞台物理联动、动作视觉归因或完整 DSH 运行时验证。
