# 鲸语 · 桌面伙伴（macOS）

把 Live2D 角色放到桌面上常驻：无边框、背景透明、默认点击穿透的浮动窗口，
加载的是同一个舞台页 `web/desktop.html`，动作引擎、模型、预设都和面板一致。

## 用

```bash
# 1. 先让 Bridge 跑起来（项目根目录）
python3 launch.py

# 2. 构建并启动桌面伙伴
cd macos-desktop-pet
./build.sh
open "build/Jingyu Desktop Pet.app"
```

需要 Xcode 命令行工具（`xcode-select --install`）。构建产物在 `macos-desktop-pet/build/`，不进 Git。

- 窗口默认出现在主屏右下角，底边贴齐；位置记在 `~/Library/Preferences/local.jingyu.desktop-pet.plist`。
- 菜单栏出现「鲸」图标：
  - **点击穿透**（默认开）：鼠标点上去会落到下面的窗口，不挡你干活。
  - 关掉穿透后：⌥+拖动移动窗口，双击角色播放一个内置示例。
  - 重新加载 / 回到默认位置 / 打开鲸语面板 / 退出。
- Bridge 没起时窗口先重试 5 次（每次 2 秒），仍失败就显示一张提示卡片，而不是留个空白窗。

## 为什么自己写原生窗口

桌面宠物需要的三件事，AppKit 直接给：

| 需求 | 实现 |
|---|---|
| 真透明 | `isOpaque = false`、`backgroundColor = .clear`、`webView.setValue(false, forKey: "drawsBackground")` |
| 浮在所有窗口与所有空间之上 | `window.level = .floating` + `collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]` |
| 不挡住下面的操作 | `ignoresMouseEvents` 由菜单栏开关控制 |

Electron 也能做，但为了一个窗口拉一整套运行时（上百 MB）不划算；这里只依赖系统自带的 WebKit，`swiftc` 编出来几百 KB。

## 分工

桌面伙伴只负责"演"：它监听 Bridge 的 `/api/events`，网页后端的计划一执行，角色就跟着动；
但它**不注册为渲染器**，所以导出 GIF/MP4 仍然由面板窗口负责，不会出现"导出到透明小窗"的错位。

## 已知边界

- macOS 上 VTS 原生帧流本来就不存在（Spout2 仅 Windows），这条对桌面伙伴同样适用。
- 窗口置于 `.floating` 层，不会盖住系统菜单栏、Dock 和锁屏。
- 高分屏下按 `devicePixelRatio` 渲染，窗口拉很大时会吃显存；常规 460×660 没有压力。