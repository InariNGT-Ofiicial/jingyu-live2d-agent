# H3 挥手动作

`wave-first.json` 与 `wave-finish.json` 是 ComfyUI API 格式。来自一次实际挥手制作的首采与二采。首遍使用四步采样并保存潜变量，第二遍读取缓存，用 H3 三维潜空间放大模型和十二步细化生成成片。Qwen3-VL-32B 对参考画面与提示词编码，H3 Ref2VA 与 Turbo v4 LoRA 生成动作，视频 VAE 解码画面。

准备兼容 MiniMax H3 参考视频、引导帧、潜变量片段缓存及 3D 放大节点的 ComfyUI 环境。两份 JSON 的 `class_type` 可与实例 `/object_info` 对照。加载节点的 `unet_name`、`clip_name`、`vae_name`、`lora_name`、`model_name` 给出了实际使用的权重文件名。该分支只含工作流，不分发模型。

把自己的正面角色图放入 `ComfyUI/input/role/front.png`。另存相同回正图为 `pose_end.png`，把三个手势引导图放为 `pose20.png`、`pose29.png`、`pose38.png`。先提交 `wave-first.json`，在输出目录确认 `role/cache_00001.safetensors` 已生成，再提交 `wave-finish.json`。同目录再次运行时，检查二采的 `finish_load.inputs.latent_path` 确实指向本次缓存。

```sh
python submit.py wave-first.json
# 在 ComfyUI 完成首采、确认缓存后
python submit.py wave-finish.json
```

将最终单机位竖屏 MP4 命名为 `wave.mp4`。其他动作复用这两个工作流，分别修改动作描述、中间姿势、种子和输出前缀。眼睛、肩膀、窗框和光照均应在首尾连续。动作验完后按[主指南](../README.md)导入。
