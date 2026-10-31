"""Read-only readiness report for the VTS backend on this host.

Answers one question: what still blocks a hot-deploy run? Every step is a plain
check with a next action, so a first macOS run does not end in a stack trace.
Nothing here writes to VTS, copies models or triggers playback unless --approve
is given (that flag only performs the normal plugin authentication prompt).
"""
import argparse, json, os, socket, stat, sys
from pathlib import Path
from model_profile import MODEL_ROOT, ROOT, read_json
import platform_support as ps

OK, WARN, BAD, SKIP = '✅', '⚠️', '❌', '·'


def report(rows):
    width = max(len(name) for name, _, _ in rows)
    for state, name, detail in rows:
        print(f'{state}  {name.ljust(width)}  {detail}')
    return rows


def steam_present():
    roots = ps.steam_roots()
    return roots[0] if roots else None


def plugin_api(port, timeout=2.0):
    with socket.create_connection(('127.0.0.1', port), timeout=timeout):
        return True


def api_state(port, timeout=6):
    from vts_client import VTS
    client = VTS(port, timeout=timeout)
    try:
        return client.call('APIStateRequest', timeout=timeout), client
    except Exception:
        client.close()
        raise


def write_state(path):
    """Separate "directory is not writable" from "this process is sandboxed"."""
    if path is None:
        return False, '（未找到 Live2DModels）'
    if os.access(path, os.W_OK):
        return True, ''
    try:
        mode = os.stat(path).st_mode
    except OSError:
        return False, '（无法读取目录属性）'
    if mode & stat.S_IWUSR:
        return False, '（属主可写，但当前进程被沙箱限制；请在有权限的终端里执行复制）'
    return False, '（目录属主不可写）'


def main():
    p = argparse.ArgumentParser(description='VTS backend readiness check (read-only)')
    p.add_argument('--port', type=int, default=8001)
    p.add_argument('--approve', action='store_true', help='run the plugin authentication prompt')
    p.add_argument('--json', action='store_true')
    a = p.parse_args()
    rows = []
    blockers = 0

    rows.append((OK, '平台', f'{ps.platform_name()} · Python {sys.version.split()[0]} · 令牌保管 {ps.token_backend()}'))
    if not ps.capture_available():
        rows.append((SKIP, '原生帧流', 'Spout2 仅 Windows；macOS 请用 NDI/OBS 或网页渲染导出'))

    try:
        import websocket  # noqa: F401
        rows.append((OK, 'websocket-client', '已安装，可连接插件 API'))
    except ImportError:
        blockers += 1
        rows.append((BAD, 'websocket-client', '未安装：python3 -m pip install -r requirements-vts.txt'))

    steam = steam_present()
    if steam:
        rows.append((OK, 'Steam', str(steam)))
    else:
        blockers += 1
        rows.append((BAD, 'Steam', '未找到 Steam 客户端（macOS 版 VTube Studio 也通过 Steam 安装）'))

    try:
        root = ps.find_vts()
        models = ps.vts_models_dir(root)
        writable, why = write_state(models)
        rows.append((OK if writable else WARN, 'VTube Studio', f'{root}' + why))
        rows.append((OK, 'Live2DModels', str(models)))
    except ValueError as error:
        blockers += 1
        rows.append((BAD, 'VTube Studio', str(error)))

    api = None
    try:
        plugin_api(a.port)
        rows.append((OK, '插件 API 端口', f'127.0.0.1:{a.port} 可达'))
        state, api = api_state(a.port)
        needs = state.get('authenticationRequired')
        rows.append((WARN if needs else OK, '插件授权',
                     '已在 VTS 中允许 "Jingyu Motion Bridge"' if not needs else 'VTS 正在等待授权'))
    except ImportError:
        blockers += 1
        rows.append((BAD, '插件 API', '缺少 websocket-client，跳过连接检查'))
    except OSError:
        blockers += 1
        rows.append((BAD, '插件 API', f'127.0.0.1:{a.port} 不可达；在 VTS 设置里开启插件 API'))
    except Exception as error:
        blockers += 1
        rows.append((BAD, '插件 API', str(error)))

    if api is not None:
        try:
            if a.approve:
                api.authenticate()
                rows.append((OK, '授权结果', f'已授权，令牌保存方式 {ps.token_backend()}'))
            current = api.call('CurrentModelRequest')
            author = read_json(MODEL_ROOT / '大肥鱼.vtube.json')['ModelID']
            if current.get('modelLoaded') and current.get('modelID') == author:
                rows.append((OK, '当前模型', 'VTS 已加载作者模型'))
            else:
                rows.append((WARN, '当前模型',
                             'VTS 当前模型不是作者模型；热部署会自行切换，但首次需确认专用副本已被 VTS 扫描到'))
        except Exception as error:
            text = str(error)
            if 'authentication' in text.lower() or '401' in text:
                rows.append((WARN, '授权结果', '尚未授权：加 --approve 触发授权弹窗，然后在 VTS 里点允许'))
            else:
                rows.append((WARN, '模型状态', text))
        finally:
            api.close()

    manifest = ROOT / 'research/vts-comparison/import-manifest.json'
    if manifest.is_file():
        data = read_json(manifest)
        dest = Path(data.get('destination', ''))
        if dest.is_dir():
            rows.append((OK, '专用副本', f'Jingyu-Author-Comparison 已就绪（{dest}）'))
        else:
            rows.append((WARN, '专用副本', '清单存在但目录不见了：python3 vts_setup.py 重建'))
    else:
        rows.append((WARN, '专用副本', '尚未创建：python3 vts_setup.py（会复制一份作者模型到 VTS，不改原目录）'))

    if not a.json:
        report(rows)
        print()
        if blockers:
            print(f'结论：{blockers} 项阻塞。修完上面的 ❌ 再跑一次。')
        else:
            print('结论：可以执行 python3 bridge_cli.py execute examples/hotdeploy-left.json --backend vts --wait')
    else:
        print(json.dumps([{'state': s, 'check': n, 'detail': d} for s, n, d in rows], ensure_ascii=False, indent=2))
    return 1 if blockers else 0


if __name__ == '__main__':
    raise SystemExit(main())