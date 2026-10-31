// Jingyu desktop companion: a transparent, click-through window that shows the
// existing web stage (/desktop.html) on top of the desktop.
//
// Why a native window instead of Electron: it needs no runtime download, and
// AppKit gives the three things a desktop pet needs — a clear background, a
// floating window level across Spaces, and per-window mouse passthrough.
import AppKit
import WebKit

let defaultPage = "http://127.0.0.1:61942/desktop.html"
let frameKey = "petWindowFrame"
let clickThroughKey = "petClickThrough"
let defaultSize = NSSize(width: 460, height: 660)

final class Bridge: NSObject, WKScriptMessageHandler {
    weak var window: NSWindow?
    weak var pet: NSWindow?

    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        guard let body = message.body as? [String: Any] else { return }
        if let error = body["error"] as? String {
            FileHandle.standardError.write("[pet] page error: \(error)\n".data(using: .utf8)!)
        }
        if body["ready"] != nil {
            pet?.alphaValue = 1
        }
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate, WKNavigationDelegate {
    private var window: NSWindow!
    private var webView: WKWebView!
    private var statusItem: NSStatusItem!
    private var bridge: Bridge!
    private var clickThrough = true
    private var page = URL(string: defaultPage)!
    private var clickItem: NSMenuItem!
    private var revealTimer: Timer?
    private var retryTimer: Timer?
    private var attempts = 0

    func applicationDidFinishLaunching(_ notification: Notification) {
        let arguments = CommandLine.arguments
        if let index = arguments.firstIndex(of: "--url"), index + 1 < arguments.count, let url = URL(string: arguments[index + 1]) {
            page = url
        }
        clickThrough = UserDefaults.standard.object(forKey: clickThroughKey) as? Bool ?? true
        buildWindow()
        buildMenu()
        installOptionDragMonitor()
    }

    private func buildWindow() {
        var frame = NSRect(origin: .zero, size: defaultSize)
        if let saved = UserDefaults.standard.string(forKey: frameKey) {
            let restored = NSRectFromString(saved)
            if restored.width > 120, restored.height > 120 { frame = restored }
        } else if let screen = NSScreen.main {
            let area = screen.visibleFrame
            frame.origin = NSPoint(x: area.maxX - frame.width - 32, y: area.minY)
        }

        let configuration = WKWebViewConfiguration()
        bridge = Bridge()
        configuration.userContentController.add(bridge, name: "pet")
        webView = WKWebView(frame: NSRect(origin: .zero, size: frame.size), configuration: configuration)
        webView.setValue(false, forKey: "drawsBackground")   // let the desktop show through
        webView.autoresizingMask = [.width, .height]

        window = NSWindow(contentRect: frame, styleMask: [.borderless], backing: .buffered, defer: false)
        window.isOpaque = false
        window.backgroundColor = .clear
        window.hasShadow = false
        window.level = .floating
        window.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary, .ignoresCycle]
        window.ignoresMouseEvents = clickThrough
        window.alphaValue = 0                               // fade in once the page is ready
        window.delegate = self
        window.contentView = webView
        bridge.pet = window
        webView.navigationDelegate = self
        window.orderFrontRegardless()

        webView.load(URLRequest(url: page))

        // Never leave an invisible window behind if the page failed to load.
        revealTimer = Timer.scheduledTimer(withTimeInterval: 8, repeats: false) { [weak self] _ in
            self?.window.alphaValue = 1
        }
    }

    private func buildMenu() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        statusItem.button?.title = "鲸"
        statusItem.button?.toolTip = "鲸语 · 桌面伙伴"

        let menu = NSMenu()
        clickItem = NSMenuItem(title: "点击穿透", action: #selector(toggleClickThrough), keyEquivalent: "")
        clickItem.target = self
        clickItem.state = clickThrough ? .on : .off
        menu.addItem(clickItem)

        let hint = NSMenuItem(title: "关闭穿透后可拖动画面、双击播放示例；⌥+拖动随时可移动窗口", action: nil, keyEquivalent: "")
        hint.isEnabled = false
        menu.addItem(hint)
        menu.addItem(.separator())

        for (title, action, key) in [("重新加载", #selector(reload), "r"), ("回到默认位置", #selector(resetPosition), "")] {
            let item = NSMenuItem(title: title, action: action, keyEquivalent: key)
            item.target = self
            menu.addItem(item)
        }
        let dashboard = NSMenuItem(title: "打开鲸语面板", action: #selector(openDashboard), keyEquivalent: "")
        dashboard.target = self
        menu.addItem(dashboard)
        menu.addItem(.separator())
        let quit = NSMenuItem(title: "退出", action: #selector(quit), keyEquivalent: "q")
        quit.target = self
        menu.addItem(quit)
        statusItem.menu = menu
    }

    // The web view consumes mouse events, so window dragging needs a shortcut
    // the native side can claim: hold ⌥ and drag anywhere.
    private func installOptionDragMonitor() {
        NSEvent.addLocalMonitorForEvents(matching: .leftMouseDown) { [weak self] event in
            guard let self, let window = self.window, event.window === window else { return event }
            guard event.modifierFlags.contains(.option) else { return event }
            window.performDrag(with: event)
            return nil
        }
    }

    @objc private func toggleClickThrough() {
        clickThrough.toggle()
        clickItem.state = clickThrough ? .on : .off
        window.ignoresMouseEvents = clickThrough
        UserDefaults.standard.set(clickThrough, forKey: clickThroughKey)
    }

    @objc private func reload() {
        attempts = 0
        webView.load(URLRequest(url: page))
    }

    // The bridge may still be starting, so retry briefly; after that say so
    // instead of leaving an invisible window with no explanation.
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        retry()
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        retry()
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        attempts = 0
    }

    private func retry() {
        attempts += 1
        retryTimer?.invalidate()
        guard attempts <= 5 else { showOfflineHint(); return }
        let target = page
        retryTimer = Timer.scheduledTimer(withTimeInterval: 2, repeats: false) { [weak self] _ in
            self?.webView.load(URLRequest(url: target))
        }
    }

    private func showOfflineHint() {
        window.alphaValue = 1
        let html = """
        <html><body style="margin:0;font:13px/1.6 -apple-system;color:#33413a;background:transparent">
        <div style="margin:24px;padding:16px 18px;border-radius:14px;background:rgba(255,255,255,.92);
                    box-shadow:0 6px 24px rgba(0,0,0,.12)">
          <b>鲸语 Bridge 没有响应</b><br>
          先在项目目录运行 <code>python3 launch.py</code>，然后点菜单栏「鲸」→ 重新加载。
          <div style="margin-top:8px;color:#7b8a80">目标地址：\(page.absoluteString)</div>
        </div></body></html>
        """
        webView.loadHTMLString(html, baseURL: nil)
    }

    @objc private func resetPosition() {
        guard let screen = NSScreen.main else { return }
        let area = screen.visibleFrame
        window.setFrame(NSRect(x: area.maxX - window.frame.width - 32, y: area.minY,
                               width: window.frame.width, height: window.frame.height), display: true)
        saveFrame()
    }

    @objc private func openDashboard() {
        var components = URLComponents(url: page, resolvingAgainstBaseURL: false)
        components?.path = "/"
        components?.query = nil
        if let url = components?.url { NSWorkspace.shared.open(url) }
    }

    @objc private func quit() { NSApp.terminate(nil) }

    private func saveFrame() {
        UserDefaults.standard.set(NSStringFromRect(window.frame), forKey: frameKey)
    }

    func windowDidMove(_ notification: Notification) { saveFrame() }
    func windowDidResize(_ notification: Notification) { saveFrame() }
    func applicationWillTerminate(_ notification: Notification) { saveFrame() }
}

@main
struct PetApp {
    static func main() {
        let app = NSApplication.shared
        let delegate = AppDelegate()
        app.delegate = delegate
        app.setActivationPolicy(.accessory)   // menu bar only, no Dock icon
        app.run()
    }
}