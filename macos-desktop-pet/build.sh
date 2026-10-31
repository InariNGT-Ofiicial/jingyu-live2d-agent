#!/bin/sh
# Build the desktop companion app bundle. Requires the Xcode command line tools.
set -e
cd "$(dirname "$0")"
APP="build/Jingyu Desktop Pet.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
swiftc -O -swift-version 5 -parse-as-library \
  -o "$APP/Contents/MacOS/jingyu-pet" \
  DesktopPet.swift -framework AppKit -framework WebKit
cp Info.plist "$APP/Contents/Info.plist"
# Ad-hoc signature keeps macOS from re-prompting on every launch.
codesign --force --sign - "$APP" >/dev/null 2>&1 || true
echo "已构建：$APP"
echo "启动：open \"$APP\""
echo "（先让鲸语 Bridge 跑起来：cd .. && python3 launch.py）"